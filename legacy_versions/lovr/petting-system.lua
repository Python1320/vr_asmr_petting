-- Description: communicates with OpenVR API to get controller location data
--
-- 
local lovr = {
	thread = require'lovr.thread',
	filesystem = require'lovr.filesystem'
}

local channel = lovr.thread.getChannel('petting-system')
local channel_tx = lovr.thread.getChannel('petting-system-tx')
lovr.filesystem.setRequirePath([[lua/?/init.lua;lua/?.lua;]] .. lovr.filesystem.getRequirePath())
local ovr = require'openvr'
local ffi = require'ffi'
local os = require'os'
local vrError = ffi.new'EVRInitError[1]'
local eTrackedPropertyError = ffi.new'ETrackedPropertyError[1]'
local buffer = require('string.buffer')
local MIN_SIZE = 65536
local sender = require'oscsender'
local config = require'config'
local util = require'util'
local started = os.time()

local function log(...)
	print(("%.4f"):format(os.time() - started), ...)
end

--util.sleep(0)
--assert(config.getBySerial('LHR-C6E6E6A8') or false, 'heck')
local function vr_init()
	::reinit::
	log('vr_init():')
	assert(ovr.VR_IsRuntimeInstalled(), "OpenVR runtime is not installed!")
	log('VR_IsHmdPresent=', ovr.VR_IsHmdPresent())
	ovr.VR_InitInternal(vrError, ovr.EVRApplicationType_VRApplication_Background)

	do
		local vrError = vrError[0]

		if vrError ~= ovr.EVRInitError_VRInitError_None then
			if vrError == ovr.EVRInitError_VRInitError_Init_NoServerForBackgroundApp then
				log("No SteamVR detected, sleeping...")
				util.sleep(2)
				goto reinit
			end

			log('vrError=', vrError, ovr.getIinitErrorString(vrError))
			error(ovr.getIinitErrorString(vrError))
		end
	end

	local fnTableName = 'FnTable:' .. tostring(ovr.IVRSystem_Version)
	--log('requesting', tostring(fnTableName))
	local fnTable = ffi.cast('struct VR_IVRSystem_FnTable*', ovr.VR_GetGenericInterface(fnTableName, vrError))

	--log('fnTable=',fnTable)
	do
		local vrError = vrError[0]

		if vrError ~= ovr.EVRInitError_VRInitError_None then
			log('vrError=', vrError, ovr.getIinitErrorString(vrError))

			return false
		end
	end

	return {
		system = fnTable
	}
end

local vr, err = vr_init()
local trackables = {}

if not vr then
	log(err)

	return os.exit(1)
end

collectgarbage'collect'
log('Let\'s goo')
local buf = buffer.new()
local ptr, len = buf:reserve(MIN_SIZE)
log('len=', len)
local biggest_id = 0

local function addDevice_enumerator(unDeviceIndex)
	buf:reset()
	local len = vr.system.GetStringTrackedDeviceProperty(unDeviceIndex, ovr.ETrackedDeviceProperty_Prop_SerialNumber_String, ptr, len, eTrackedPropertyError)
	buf:commit(math.max(0, len - 1))

	do
		local eTrackedPropertyError = eTrackedPropertyError[0]

		if eTrackedPropertyError ~= ovr.ETrackedPropertyError_TrackedProp_InvalidDevice then
			if eTrackedPropertyError ~= ovr.ETrackedPropertyError_TrackedProp_Success then
				log('eTrackedPropertyError=', eTrackedPropertyError)
				error("eTrackedPropertyError " .. tostring(eTrackedPropertyError))
			end
		else
		end
		-- can we break here? probably not, there may be gaps.
		--print(unDeviceIndex)
	end

	if len > 0 then
		local serial = tostring(buf)
		log('id', unDeviceIndex, 'serial=', '\'' .. serial .. '\'')
		local conf = config.getBySerial(serial)

		if conf then
			trackables[unDeviceIndex] = conf
			biggest_id = math.max(biggest_id, unDeviceIndex)
			log('TRACKING', serial)
		end
	end
end

for unDeviceIndex = 0, tonumber(ovr.k_unMaxTrackedDeviceCount) do
	addDevice_enumerator(unDeviceIndex)
end

local trackedDevicePoseArray = ffi.new('TrackedDevicePose_t[' .. (biggest_id + 1) .. ']')
local trackedDevices = table.count(trackables)
assert(trackedDevices > 0, "Error: Did not find trackable devices")
assert(trackedDevices <= biggest_id)
log('trackedDevices=', trackedDevices, 'biggest_id=', biggest_id)

local payload_f = {
	address = '/foo/bar',
	types = 'f',
	0
}

local function track(unDeviceIndex, trackable, debug_state)
	local serial, osc_message = unpack(trackable)
	local pose = trackedDevicePoseArray[unDeviceIndex]

	if not trackable.tracking then
		trackable.tracking = true
		trackable.bDeviceIsConnected = false
		trackable.bPoseIsValid = false
		log('Now tracking:', serial)
	end

	if pose.bDeviceIsConnected ~= trackable.bDeviceIsConnected then
		trackable.bDeviceIsConnected = pose.bDeviceIsConnected
		log('bDeviceIsConnected:', serial, pose.bDeviceIsConnected)
	end

	if pose.bPoseIsValid ~= trackable.bPoseIsValid then
		trackable.bPoseIsValid = pose.bPoseIsValid
		log('bPoseIsValid:', serial, pose.bPoseIsValid)
	end

	if not pose.bDeviceIsConnected then return end
	if not pose.bPoseIsValid then return end
	local speed = math.sqrt(pose.vAngularVelocity.v[0] ^ 2 + pose.vAngularVelocity.v[1] ^ 2 + pose.vAngularVelocity.v[2] ^ 2)*0.1
	speed = math.min(math.max(speed, 0), 1)
	--log(osc_message, speed)
	payload_f.address = osc_message
	payload_f[1] = speed
	debug_state[osc_message] = speed
	sender.send(payload_f)
end

local _M = {}

function _M.start()
	_M.receiver = sender.start_receiver()
end

local acc = 0

function _M.update(dt, debug_state)
	local ret, err = coroutine.resume(_M.receiver)

	if not ret then
		error(debug.traceback(_M.receiver, err))
	end

	acc = acc + dt
	if acc < 0.1 then return end -- only update at 10hz
	acc = acc % 0.1 --TODO: check for missed frames
	vr.system.GetDeviceToAbsoluteTrackingPose(ovr.ETrackingUniverseOrigin_TrackingUniverseRawAndUncalibrated, 0, trackedDevicePoseArray, biggest_id + 1)

	for unDeviceIndex, trackable in pairs(trackables) do
		track(unDeviceIndex, trackable, debug_state)
	end
end

return _M