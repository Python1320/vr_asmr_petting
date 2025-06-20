local table = require 'ext.table'

return function(args)
	return require 'vec-ffi.create_vec'(table(args, {
		dim = 2,
		classCode = [[
cl.angle = function(v)
	return math.atan2(v.y, v.x)
end

cl.determinant = function(a,b)
	return a.x * b.y - a.y * b.x
end

-- such that v:perpendicular():dot(w) = vec2.determinant(v,w) = area of parallelogram with sides v & w
cl.perpendicular = function(v)
	return metatype(-v.y, v.x)
end
]],
	}))
end
