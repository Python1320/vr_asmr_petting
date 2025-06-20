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
local sock = require'sock'
local started = os.time()

local function log(...)
	print(("%.4f"):format(os.time() - started), ...)
end

--util.sleep(0)
--assert(config.getBySerial('LHR-C6E6E6A8') or false, 'heck')
local function vr_init()
	log('loading VR')
	log('VR_IsHmdPresent=', ovr.VR_IsHmdPresent())
	log('VR_IsRuntimeInstalled=', ovr.VR_IsRuntimeInstalled())
	ovr.VR_InitInternal(vrError, ovr.EVRApplicationType_VRApplication_Background)

	do
		local vrError = vrError[0]

		if vrError ~= ovr.EVRInitError_VRInitError_None then
			log('vrError=', vrError, ovr.getIinitErrorString(vrError))

			return false
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

while true do end 
for unDeviceIndex = 0, tonumber(ovr.k_unMaxTrackedDeviceCount) do
	buf:reset()
	local len = vr.system.GetStringTrackedDeviceProperty(unDeviceIndex, ovr.ETrackedDeviceProperty_Prop_SerialNumber_String, ptr, len, eTrackedPropertyError)
	buf:commit(math.max(0, len - 1))

	do
		local eTrackedPropertyError = eTrackedPropertyError[0]

		if eTrackedPropertyError ~= ovr.ETrackedPropertyError_TrackedProp_Success then
			log('eTrackedPropertyError=', eTrackedPropertyError)

			return false
		end
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

local trackedDevicePoseArray = ffi.new('TrackedDevicePose_t[' .. (biggest_id + 1) .. ']')
local trackedDevices = table.count(trackables)
assert(trackedDevices <= biggest_id)
log('trackedDevices=', trackedDevices, 'biggest_id=', biggest_id)

local payload_f = {
	address = '/foo/bar',
	types = 'f',
	0
}

local function track(unDeviceIndex, trackable)
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
	-- https://github.com/ValveSoftware/openvr/wiki/Matrix-Usage-Example
	-- 
	local speed = math.sqrt(pose.vAngularVelocity.v[0] ^ 2 + pose.vAngularVelocity.v[1] ^ 2 + pose.vAngularVelocity.v[2] ^ 2)
	speed = math.min(math.max(speed, 0), 1)
	--log(osc_message, speed)
	payload_f.address = osc_message
	payload_f[1] = speed
	sender.sendMessage(payload_f)
end

local sock = require'sock'

local receive_co = sock.newthread(function()
	print("receiving")
	sock.sleep(0)
	print("receiving")
	sender.startReceiving()
	print("received end")
end)
sock.run(function()
	sock.resume(receive_co)

	while true do
		vr.system.GetDeviceToAbsoluteTrackingPose(ovr.ETrackingUniverseOrigin_TrackingUniverseRawAndUncalibrated, 0, trackedDevicePoseArray, biggest_id + 1)

		for unDeviceIndex, trackable in pairs(trackables) do
			track(unDeviceIndex, trackable)
		end
		
		sock.sleep(0.1) -- about 10hz refresh rate is maximum anyway. TODO: socket.sleep to allow server to run also
	end
end)

log('done')