local suffix = require 'vec-ffi.suffix'

return function(ctype)
	return require 'vec-ffi.create_vec'{
		dim = 4,
		ctype = ctype,
		vectype = 'quat'..suffix[ctype]..'_t',

		-- create the 3type associated with our quat 4type
		vec3require = 'vec-ffi.vec3'..suffix[ctype],

-- TODO allow self.references somehow
-- how about a callback to modify cl?
-- but then you need to pass in the whole function environment ...
		classCode = [[
local vec3 = require '<?=vec3require?>'

cl.mul = function(q, r, res)
	if not res then res = metatype() end

	local a = (q.w + q.x) * (r.w + r.x)
	local b = (q.z - q.y) * (r.y - r.z)
	local c = (q.x - q.w) * (r.y + r.z)
	local d = (q.y + q.z) * (r.x - r.w)
	local e = (q.x + q.z) * (r.x + r.y)
	local f = (q.x - q.z) * (r.x - r.y)
	local g = (q.w + q.y) * (r.w - r.z)
	local h = (q.w - q.y) * (r.w + r.z)

	res.x = a - .5 * ( e + f + g + h)
	res.y = -c + .5 * ( e - f + g - h)
	res.z = -d + .5 * ( e - f - g + h)
	res.w = b + .5 * (-e - f + g + h)

	return res
end

cl.__mul = cl.mul

cl.__div = function(a,b)
	return a * b:conjugate() / b:lenSq()
end

-- in degrees
cl.toAngleAxis = function(self, res)
	if not res then res = metatype() end

	local cosom = math.clamp(self.w, -1, 1)

	local halfangle = math.acos(cosom)
	local scale = math.sin(halfangle)

	if scale >= -.00001 and scale <= .00001 then
		res.x = 0
		res.y = 0
		res.z = 1
		res.w = 0
	else
		scale = 1 / scale
		res.x = self.x * scale
		res.y = self.y * scale
		res.z = self.z * scale
		res.w = halfangle * 360 / math.pi
	end

	return res
end

-- TODO epsilon-test this?  so no nans?
cl.fromAngleAxis = function(q, x, y, z, degrees)
	local vlen = math.sqrt(x*x + y*y + z*z)
	local radians = math.rad(degrees)
	local costh = math.cos(radians / 2)
	local sinth = math.sin(radians / 2)
	local vscale = sinth / vlen
	q.x = x * vscale
	q.y = y * vscale
	q.z = z * vscale
	q.w = costh
	return q
end

cl.xAxis = function(q, res)
	if not res then res = vec3() end
	res.x = 1 - 2 * (q.y * q.y + q.z * q.z)
	res.y = 2 * (q.x * q.y + q.z * q.w)
	res.z = 2 * (q.x * q.z - q.w * q.y)
	return res
end

cl.yAxis = function(q, res)
	if not res then res = vec3() end
	res.x = 2 * (q.x * q.y - q.w * q.z)
	res.y = 1 - 2 * (q.x * q.x + q.z * q.z)
	res.z = 2 * (q.y * q.z + q.w * q.x)
	return res
end

cl.zAxis = function(q, res)
	if not res then res = vec3() end
	res.x = 2 * (q.x * q.z + q.w * q.y)
	res.y = 2 * (q.y * q.z - q.w * q.x)
	res.z = 1 - 2 * (q.x * q.x + q.y * q.y)
	return res
end

-- TODO instead of a table-of-vec3_t's, how about a matrix ffi type?
cl.toMatrix = function(q, mat)
	if not mat then mat = {} end
	mat[1] = metatype.xAxis(q, mat[1])
	mat[2] = metatype.yAxis(q, mat[2])
	mat[3] = metatype.zAxis(q, mat[3])
	return mat
end

-- vec-ffi's quat's fromMatrix uses col-major Lua-table-of-vec3s (just like 'toMatrix')
-- https://math.stackexchange.com/a/3183435/206369
cl.fromMatrix = function(q, mat)
	local m00, m01, m02 = mat[1]:unpack()
	local m10, m11, m12 = mat[2]:unpack()
	local m20, m21, m22 = mat[3]:unpack()
	local t
	if m22 < 0 then
		if m00 > m11 then
			t = 1 + m00 - m11 - m22
			q.x = t
			q.y = m01+m10
			q.z = m20+m02
			q.w = m12-m21
		else
			t = 1 - m00 + m11 - m22
			q.x = m01+m10
			q.y = t
			q.z = m12+m21
			q.w = m20-m02
		end
	else
		if m00 < -m11 then
			t = 1 - m00 - m11 + m22
			q.x = m20+m02
			q.y = m12+m21
			q.z = t
			q.w = m01-m10
		else
			t = 1 + m00 + m11 + m22
			q.x = m12-m21
			q.y = m20-m02
			q.z = m01-m10
			q.w = t
		end
	end
	assert(t, "somehow we missed this")
	q.x = q.x * .5 / math.sqrt(t)
	q.y = q.y * .5 / math.sqrt(t)
	q.z = q.z * .5 / math.sqrt(t)
	q.w = q.w * .5 / math.sqrt(t)
	return q
end

cl.rotate = function(self, v, res)
	res = res or vec3()
	-- TODO get rid of the extra object creations
	local v4 = self * metatype(v.x, v.y, v.z, 0) * self:conjugate()
	res.x = v4.x
	res.y = v4.y
	res.z = v4.z
	return res
end

function cl:conjugate(res)
	res = res or metatype()
	res.x = -self.x
	res.y = -self.y
	res.z = -self.z
	res.w = self.w
	return res
end

cl.normalizeEpsilon = 1e-7

function cl:normalize(res, eps)
	eps = eps or cl.normalizeEpsilon
	res = res or metatype()
	local lenSq = self:normSq()
	if lenSq < eps*eps then
		res.x = 0
		res.y = 0
		res.z = 0
		res.w = 1
	else
		local invlen = 1 / math.sqrt(lenSq)
		res.x = self.x * invlen
		res.y = self.y * invlen
		res.z = self.z * invlen
		res.w = self.w * invlen
	end
	return res
end
]],
	}
end
