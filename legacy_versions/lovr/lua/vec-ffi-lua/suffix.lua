local table = require 'ext.table'

local suffix = {
	char = 'b',
	short = 's',
	int = 'i',
	long = 'l',
	size_t = 'sz',
	float = 'f',
	double = 'd',
}

for _,k in ipairs(table.keys(suffix)) do
	suffix['unsigned '..k] = 'u'..suffix[k]
end

return suffix
