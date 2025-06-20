local table = require 'ext.table'
local template = require 'template'
local showcode = require 'template.showcode'
local suffixes = require 'vec-ffi.suffix'

return function(vectype)
	assert(vectype)

	local dim = vectype.dim
	local ctype = vectype.elemType
	local suffix = suffixes[ctype]

	local args = {
		dim = dim,
		suffix = suffix,
		ctype = ctype,
		vectype = vectype,
		-- TODO remove the _t ?
		boxtype = 'box'..dim..suffix..'_t',
		fields = table{'min', 'max'},
	}

	local code = template([=[
<?
local range = require 'ext.range'
?>
-- class to match 'vectype'
local args = ...
local vectype = args.vectype
local dim = args.dim
local ffi = require 'ffi'

local typeCode = [[
typedef union <?=boxtype?> {
	struct {
		<?=vectype.type?> <?=fields:concat', '?>;
	};
	<?=vectype.type?> s[2];
} <?=boxtype?>;
]]

ffi.cdef(typeCode)
assert(ffi.sizeof'<?=boxtype?>' == 2 * ffi.sizeof'<?=vectype.type?>')

local metatype
local cl = {
	sizeof = ffi.sizeof('<?=boxtype?>'),
	type = '<?=boxtype?>',	-- TODO 'name' ?
	elemType = '<?=vectype.type?>',
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
	-- TODO how to unpack box?  as two tables, or flattened?
	unpack = function(self)
		return <?=fields:mapi(function(x) return 'self.'..x..':toTable()' end):concat', '?>
	end,

	-- TODO between this and ffi.cpp.vector, one is toTable the other is totable ... which to use?
	-- duplicated from vec-ffi.create_vec
	toTable = function(self)
		return {self:unpack()}
	end,

	__eq = function(a,b)
		if not (type(a) == 'table' or type(a) == 'cdata')
		or not (type(b) == 'table' or type(b) == 'cdata')
		then
			return false
		end
		return <?=fields:mapi(function(x) return 'a.'..x..' == '..'b.'..x end):concat(' and ')?>
	end,

	__tostring = function(v)
		return '(' .. <?=
			fields:mapi(function(x)
				return 'tostring(v.'..x..')'
			end):concat(' .. ", " .. ')
		?> .. ')'
	end,

	__concat = function(a, b)
		return tostring(a) .. tostring(b)
	end,


-- from here on our, box-specific functions:

	__mul = function(a,b)
		if metatype:isa(a) and type(b) == 'number' then
			return metatype(a.min * b, a.max * b)
		elseif type(a) == 'number' and metatype:isa(b) then
			return metatype(a * b.min, a * b.max)
		else
			error"don't know how to multiply bbox with this"
		end
	end,

	-- static initializer for empty box
	empty = function()
		return metatype(
			vectype(<?=range(dim):mapi(function() return 'math.huge' end):concat', '?>),
			vectype(<?=range(dim):mapi(function() return '-math.huge' end):concat', '?>)
		)
	end,

	size = function(self)
		return self.max - self.min
	end,

	-- 'b' is a 'box3', clamps 'self' to be within 'b'
	clamp = function(self, b)
		for i=0,dim-1 do
			if self.min.s[i] < b.min.s[i] then self.min.s[i] = b.min.s[i] end
			if self.max.s[i] > b.max.s[i] then self.max.s[i] = b.max.s[i] end
		end
		return self
	end,

	-- 'v' is a vec3, stretches 'self' to contain 'v'
	-- TODO same could be done with a box, stretch self's min by b's min, stretch self's max by b's max
	stretch = function(self, ...)
		local vmin, vmax
		local n = select('#', ...)
		if n == 0 then
			error("box.stretch needs an arg")
		elseif n == 1 then
			local varg = ...
			-- <?=boxtype?>:isa(varg) won't cast between boxtypes ...
			-- wish luajit behavior had stuck to Lua convention of returning nil (fast) over throwing errors (slow) for simple things like accessing fields or detecting types ...
			if type(varg) == 'cdata' and tostring(ffi.typeof(varg)):sub(1,15) == 'ctype<union box' then
				vmin, vmax = varg.min, varg.max
			else
				vmin, vmax = varg, varg
			end
		else
			vmin, vmax = ...
		end
		for i=0,dim-1 do
			self.min.s[i] = math.min(self.min.s[i], vmin.s[i])
			self.max.s[i] = math.max(self.max.s[i], vmax.s[i])
		end
	end,

	-- get the i'th corner, i in [0, 2^dim)
	corner = function(self, i)
		local v = vectype()
		for j=0,dim-1 do
			local side = bit.band(bit.rshift(i, j), 1) == 1
			v.s[j] = side and self.min.s[j] or self.max.s[j]
		end
		return v
	end,

	contains = function(self, ...)
		local vmin, vmax
		local n = select('#', ...)
		if n == 0 then
			error("box.stretch needs an arg")
		elseif n == 1 then
			local varg = ...
			-- <?=boxtype?>:isa(varg) won't cast between boxtypes ...
			if (type(varg) == 'cdata' or type(varg) == 'table')
			-- NOTICE if varg is cdata then the next test will error upon failure
			-- because luajit decided to error on invalid index instead of lua's just-return-nil behavior
			and varg.min
			and varg.max
			then
				vmin, vmax = varg.min, varg.max
			else
				vmin, vmax = varg, varg
			end
		else
			vmin, vmax = ...
		end
		for i=0,dim-1 do
			if vmin.s[i] < self.min.s[i] or vmax.s[i] > self.max.s[i] then return false end
		end
		return true
	end,

	touches = function(self, ...)
		local vmin, vmax
		local n = select('#', ...)
		if n == 0 then
			error("box.stretch needs an arg")
		elseif n == 1 then
			local varg = ...
			-- <?=boxtype?>:isa(varg) won't cast between boxtypes ...
			if (type(varg) == 'cdata' or type(varg) == 'table') and varg.min and varg.max then
				vmin, vmax = varg.min, varg.max
			else
				vmin, vmax = varg, varg
			end
		else
			vmin, vmax = ...
		end
		for i=0,dim-1 do
			if vmin.s[i] > self.max.s[i] or vmax.s[i] < self.min.s[i] then return false end
		end
		return true
	end,

	-- returns the coefficient of intersection of line segment from a to b
	intersectLineSeg = function(self, a, b)
--print('self', self)
		if self:contains(a) then return 0 end
--print('a', a)
--print('b', b)
		local d = b - a
--print('d', d)
		local bestS
		for i=0,dim-1 do
--print('test side', i)
			-- a_i + s * (b_i - a_i) = min or max = m
			-- s = (m - a_i) / (b_i - a_i)
			local s
			if d.s[i] > 0 then	-- test for collision with min
--print('di', d.s[i], 'ai', a.s[i], 'min', self.min.s[i])
				s = (self.min.s[i] - a.s[i]) / d.s[i]
			elseif d.s[i] < 0 then -- test for collision with max
--print('di', d.s[i], 'ai', a.s[i], 'max', self.max.s[i])
				s = (self.max.s[i] - a.s[i]) / d.s[i]
			end
--print('s',s)
			if s and s >= 0 and s <= 1 then
				local p = a + d * s
--print('p', p)
				local oob
				for j=0,dim-2 do
					local k = (i+j+1)%dim
					if p.s[k] < self.min.s[k] or p.s[k] > self.max.s[k] then
						oob = true
						break
					end
				end
				if not oob then
					if not bestS or s < bestS then
						bestS = s
					end
				end
			end
		end
		return bestS
	end,
}

-- [[ throws errors if the C field isn't present
cl.__index = cl
--]]
--[[ doesn't throw errors if the C field isn't present.  probably runs slower.
cl.__index = function(t,k) return cl[k] end
--]]

metatype = ffi.metatype('<?=boxtype?>', cl)
return metatype
	]=], args)
	local func, msg = load(code)
	if not func then
		error('\n'..showcode(code)..'\n'..msg)
	end
	return func(args)
end
