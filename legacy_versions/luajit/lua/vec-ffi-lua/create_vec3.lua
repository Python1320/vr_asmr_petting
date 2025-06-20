local table = require 'ext.table'

return function(args)
	return require 'vec-ffi.create_vec'(table(args, {
		dim = args.dim or 3,	-- allow override, for vec4 to inherit vec3's routines, etc

		classCode = [[

cl.determinant = function(a,b,c)
	-- return a:cross(b):dot(c)
	return a.x * b.y * c.z
		+ a.y * b.z * c.x
		+ a.z * b.x * c.y
		- a.z * b.y * c.x
		- a.y * b.x * c.z
		- a.x * b.z * c.y
end

-- such that a:cross(b):dot(c) = metatype.determinant(a,b,c) = volume of parallelepiped with sides a,b,c
cl.cross = function(a,b)
	return metatype(
		a.y * b.z - a.z * b.y,
		a.z * b.x - a.x * b.z,
		a.x * b.y - a.y * b.x)
end

-- 2D has 'perpendicular' for just rotating 90' left
-- this is going to calc e_ijk n^i and pick the best 2 of 3 columns
cl.perpendicular = function(n)
	local nx = n:cross(metatype(1,0,0))	-- TODO static?
	local ny = n:cross(metatype(0,1,0))
	local nz = n:cross(metatype(0,0,1))
	local lx = nx:normSq()
	local ly = ny:normSq()
	local lz = nz:normSq()
	local n2
	if lx > ly then 	-- lx > ly
		if lx > lz then		-- lx > lz, lx > ly
			return nx / math.sqrt(lx)
		else	-- lz >= lx > ly
			return nz / math.sqrt(lz)
		end
	else	-- ly >= lx
		if ly > lz then	-- ly >= lx, ly > lz
			return ny / math.sqrt(ly)
		else	-- lz >= ly >= lx
			return nz / math.sqrt(lz)
		end
	end
end

-- if you want to calculate the 2nd basis as well
-- n:cross(n2) should already be normalized since they are at 90' angles
function cl.perpendicular2(n)
	local n2 = n:perpendicular()
	return n2, n:cross(n2), n
end

]],
	}))
end
