local table = require 'ext.table'
local template = require 'template'
local showcode = require 'template.showcode'
local suffix = require 'vec-ffi.suffix'

--[[
args:
	dim = vector dimension
	ctype = vector element type
	vectype = (optional) vector class name.	 default = vec<dim><suffix>_t
	fields = (optional) list of fields to use.  default = xyzw.
	suffix = (optional) suffix of classname.  defaults are above.
	classCode = (optional) additional functions to put in the metatable
--]]
return function(args)
	assert(args)
	args = table(args)
	assert(args.dim)
	assert(args.ctype)
	args.suffix = args.suffix or suffix[args.ctype]
	args.classCode = args.classCode or ''
	args.vectype = args.vectype or 'vec'..args.dim..args.suffix..'_t'
	args.fields = (args.fields or table{'x', 'y', 'z', 'w'}):sub(1, args.dim)
	local code = template([=[
local ffi = require 'ffi'
local math = require 'ext.math'
local args = ...
local dim = args.dim
local vectype = args.vectype
local ctype = args.ctype

local typeCode = [[
typedef union <?=vectype?> {
	//struct has to come first for the ffi api to allow component initialization
	struct {
		<?=ctype?> <?=fields:concat', '?>;
	};

	//OpenCL compat
	struct {
		<?=ctype?> <?=require 'ext.range'(0,dim-1):mapi(function(i) return 's'..i end):concat', '?>;
	};

	<?=ctype?> s[<?=dim?>];
} <?=vectype?>;
]]

ffi.cdef(typeCode)
assert(ffi.sizeof'<?=vectype?>' == <?=dim?> * ffi.sizeof'<?=ctype?>')

local metatype

local cl = {
	sizeof = ffi.sizeof('<?=vectype?>'),
	type = vectype,	-- TODO maybe 'name' is better?
	elemType = ctype,
	dim = dim,

	typeCode = typeCode,

	-- matches behavior ext.class
	-- but ofc no inheritence
	isa = function(o)
		return type(o) == 'cdata'
		and ffi.typeof(o) == metatype
	end,

	unpack = function(self)
		return <?=fields:mapi(function(x) return 'self.'..x end):concat(', ')?>
	end,

	-- TODO between this and ffi.cpp.vector, one is toTable the other is totable ... which to use?
	toTable = function(self)
		return {self:unpack()}
	end,

	clone = function(self)
		return metatype(self:unpack())
	end,

	-- TODO no more :set on cdata or table, just on raw values
	-- use separate methods for the others
	-- prevent some if conditions
	set = function(self, v, v2, ...)
		if type(v) == 'cdata' then
			<?=fields:mapi(function(x) return 'self.'..x..' = v.'..x end):concat(' ')?>
		elseif type(v) == 'table' then
			<?=fields:mapi(function(x,key) return 'self.'..x..' = v['..key..']' end):concat(' ')?>
		else
			if v2 == nil then
				<?=fields:mapi(function(x,key) return 'self.'..x..' = v' end):concat(' ')?>
			else
				local args = {v, v2, ...}
				assert(#args >= <?=dim?>)
				<?=fields:mapi(function(x,key) return 'self.'..x..' = args['..key..']' end):concat(' ')?>
			end
		end
		return self
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


-- from here on our, vec-specific functions:


<? -- operations that are per-component or scalar
local table = require 'ext.table'
local op = require 'ext.op'

local opnames = table{
	'add', 'sub', 'mul', 'div', 'mod', 'pow',
	-- >= 5.3
	'idiv', 'band', 'bor', 'bxnot', 'shl', 'shr',
}

local opinfos = opnames:mapi(function(name,_,t)
	local symbol = op.symbols[name]
	if symbol then
		return {name=name, symbol=symbol}, #t+1
	end
end)

-- TODO unary operators

for _,info in ipairs(opinfos) do
?>	__<?=info.name?> = function(a,b)
		if type(b) == 'cdata' then
			if type(a) == 'number' then
				return metatype(<?=fields:mapi(function(x)
					return 'a'..info.symbol..'b.'..x
				end):concat(', ')?>)
			end
			return metatype(<?=fields:mapi(function(x)
				return 'a.'..x..info.symbol..'b.'..x
			end):concat(', ')?>)
		end
		b = tonumber(b)
		if b == nil then
			error("can't handle "..tostring(b).." (type "..type(b)..")")
		end
		return metatype(<?=fields:mapi(function(x)
			return 'a.'..x..info.symbol..'b'
		end):concat(', ')?>)
	end,
<? end
?>
	__unm = function(v)
		return v * -1
	end,

	map = function(v, m)
		return metatype(<?=
			fields:mapi(function(x,i)
				return 'm(v.'..x..', '..(i-1)..')'
			end):concat', '
		?>)
	end,

	lenSq = function(a)
		return a:dot(a)
	end,
	length = function(a)
		return math.sqrt(a:lenSq())
	end,

	dot = function(a,b)
		return <?=
fields:mapi(function(x) return 'a.'..x..' * b.'..x end):concat(' + ')
?>	end,

	normalize = function(v)
		return v / v:length()
	end,

	-- naming compat with Matlab/matrix
	normSq = function(a)
		return a:dot(a)
	end,
	norm = function(a)
		return math.sqrt(a:lenSq())
	end,
	unit = function(v)
		return v / v:length()
	end,

	unitOrZeroEpsilon = 1e-7,

	-- useful for surface normal / quaternion angle/axis
	unitOrZero = function(v, eps)
		eps = eps or metatype.unitOrZeroEpsilon
		local vlen = v:norm()
		if vlen <= eps or not math.isfinite(vlen) then
			return metatype(), vlen
		end
		return v / vlen, vlen
	end,

	lInfLength = function(v)	-- L-infinite length
		local fp = v.s
		local dist = math.abs(fp[0])
		for i=1,<?=dim?>-1 do
			dist = math.max(dist, math.abs(fp[i]))
		end
		return dist
	end,

	l1Length = function(v)	--L-1 length
		local fp = v.s
		local dist = math.abs(fp[0])
		for i=1,<?=dim?>-1 do
			dist = dist + math.abs(fp[i])
		end
		return dist
	end,

	-- TODO call this 'product'
	volume = function(v)
		return <?=fields:mapi(function(x) return 'v.'..x end):concat(' * ')?>
	end,

	-- normal first so the function arguments can be 1:1 with plane project
	project = function(n, v)
		return v - n * (n:dot(v) / n:dot(n))
	end,
}

-- allow the caller to override/add any functions
]=]..args.classCode..[=[

-- [[ throws errors if the C field isn't present
cl.__index = cl
--]]
--[[ doesn't throw errors if the C field isn't present.  probably runs slower.
-- but this doesn't help by field detect in the case of cdata unless every single cdef metamethod __index is set to a function instead of a table...
cl.__index = function(t,k) return cl[k] end
--]]

metatype = ffi.metatype('<?=vectype?>', cl)

return metatype
]=], args)
	local func, msg = load(code)
	if not func then
		error('\n'..showcode(code)..'\n'..msg)
	end
	return func(args)
end
