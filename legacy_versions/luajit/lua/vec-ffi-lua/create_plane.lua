local table = require 'ext.table'
local template = require 'template'
local showcode = require 'template.showcode'
local suffixes = require 'vec-ffi.suffix'

return function(args)
	local dim = assert(args.dim)
	local ctype = assert(args.ctype)

	local suffix = suffixes[ctype]
	args.suffix = suffix
	local vecNType = require('vec-ffi.vec'..dim..suffix)
	args.vecNType = vecNType
	-- TODO cache these classes somewhere better, where you don't need a new file for each new ctype?
	-- how about within create_vec?
	-- TODO remove the _t ?
	args.planeType = 'plane'..dim..suffix..'_t'
	args.vecNPlusOneType = require('vec-ffi.vec'..(dim+1)..suffix)

	args.fields = table{'n', 'negDist'}

	local code = template([=[
local args = ...
local ffi = require 'ffi'
<?
local range = require 'ext.range'
local dim = vecNType.dim
?>

local dim = <?=dim?>

local typeCode = [[
typedef union <?=planeType?> {
	struct {
		<?=vecNType.type?> n;
		<?=ctype?> negDist;
	};
	<?=vecNPlusOneType.type?> v;
	<?=ctype?> s[<?=dim+1?>];
} <?=planeType?>;
]]

ffi.cdef(typeCode)
assert(ffi.sizeof'<?=planeType?>' == ffi.sizeof'<?=vecNPlusOneType.type?>')

local metatype
local cl = {
	sizeof = ffi.sizeof('<?=planeType?>'),
	type = '<?=planeType?>',	-- TODO 'name' ?
	elemType = '<?=ctype?>',

	-- this is the dimension the plane resides in
	-- so the plane is dim+1 elements
	dim = dim,

	typeCode = typeCode,

	-- matches behavior ext.class
	-- but ofc no inheritence
	-- duplicated from vec-ffi.create_vec
	isa = function(o)
		return type(o) == 'cdata'
		and ffi.typeof(o) == metatype
	end,

	-- duplicated from vec-ffi.create_vec
	unpack = function(self)
		return self.v:unpack()
	end,

	-- TODO between this and ffi.cpp.vector, one is toTable the other is totable ... which to use?
	-- duplicated from vec-ffi.create_vec
	toTable = function(self)
		return {self.v:unpack()}
	end,

	__eq = function(a,b)
		if not (type(a) == 'table' or type(a) == 'cdata')
		or not (type(b) == 'table' or type(b) == 'cdata')
		then
			return false
		end
		return <?=fields:mapi(function(x) return 'a.'..x..' == '..'b.'..x end):concat(' and ')?>
	end,

	__tostring = function(self)
		return '(' .. <?=
			fields:mapi(function(x)
				return 'tostring(self.'..x..')'
			end):concat(' .. ", " .. ')
		?> .. ')'
	end,

	__concat = function(a, b)
		return tostring(a) .. tostring(b)
	end,


-- from here on our, plane-specific functions:

	__unm = function(self)
		return metatype(-self.n, -self.negDist)
	end,

	-- (x - pt) dot dir > 0
	-- x dot dir - pt dot dir > 0
	-- let p_i = dir_i
	-- and p_w = -pt dot dir
	-- x_i p_i + p_w > 0
	fromDirPt = function(self, dir, pt)
		-- normalize?
		self.n = dir:normalize()
		self:setPt(pt)
		return self
	end,

	setPt = function(self, pt)
		self.negDist = -pt:dot(self.n)
	end,

	-- get a point on the plane closest to origin
	-- plane eqn: v . n + negDist = 0
	-- let v = -n * negDist / (n . n)
	-- (-n * negDist / (n . n)) . n = -negDist
	-- -negDist = -negDist
	-- true
	getPt = function(self)
		return -self.n * self.negDist / self.n:lenSq()
	end,

	dist = function(self, pt)
		return self.n:dot(pt) + self.negDist
	end,

	test = function(self, pt)
		return self:dist(pt) >= 0
	end,

	-- project point x onto plane:
	-- x' = x - c n
	-- s.t. x' . n + negDist = 0
	-- (x - c n) . n + negDist = 0
	-- x . n - c n . n + negDist = 0
	-- c = (negDist + x.n) /  (n.n)
	-- c = dist(x) /  (n.n)
	-- x' = x - n * dist(x) / n.n
	-- x' = x - n * (x.n + negDist) / n.n
	-- x' = x - n * x.n / n.n - n * negDist / n.n
	-- x' = project(n,x) - n * negDist / n.n
	project = function(self, x)
		return x - self.n * (self:dist(x) / self.n:lenSq())
	end,

	-- project a vector v onto plane
	-- v' . n = 0
	-- v' = v - n (v . n) / (n . n)
	-- v . n - n . n (v . n) / (n.n) = 0
	-- 0 = 0
	-- but this is a vec3 function, not a plane3 function
	projectVec = function(self, v)
		return self.n:project(v)
	end,

	-- pt and dir are the ray's point and direction
	intersectRay = function(self, pt, dir)
		-- ((rayPos + s * rayDir) - planePt) dot planeNormal = 0
		-- rayPos dot planeNormal + s * rayDir dot planeNormal - planePt dot planeNormal = 0
		-- s = ((planePt - rayPos) dot planeNormal) / (rayDir dot planeNormal)
		local s = (self:getPt() - pt):dot(self.n) / self.n:dot(dir)
		return pt + dir * s, s
	end,

	-- transform a plane by a 4x4 matrix
	-- 3D plane test:
	-- p_i v_i + p_w > 0
	-- 3D transformed point / plane test:
	-- p_i M3_ij v_j + p_w > 0
	-- p'_i v_i + p_w > 0
	-- for p'_j = p_i M3_ij
	-- 3x4 transformed point / plane test:
	-- for M4_ij (v_j, 1) = M3_ij v_j + M4_i
	-- p_i (M3_ij v_j + M4_i) + p_w > 0
	-- (p_i M3_ij) v_j + (p_i M4_i + p_w) > 0
	-- so p'_j = p_i M3_ij
	-- and p'_w = p_i M4_i + p_w
	transform = function(self, m3x3, m4)
		self.negDist = self.negDist + self.n:dot(m4)
		self.n = self.n * m3x3
	end,
}

cl.__index = cl
metatype = ffi.metatype('<?=planeType?>', cl)
return metatype
	]=], args)
	local func, msg = load(code)
	if not func then
		error('\n'..showcode(code)..'\n'..msg)
	end
	return func(args)
end

