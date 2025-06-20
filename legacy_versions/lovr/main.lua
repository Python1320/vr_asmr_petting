
local app = require "app-vrpets"
print("Loading: main.lua")


function lovr.load()
    print("Loading: lovr.load()")
	app.load()
end

function lovr.update( dt )
	app.update( dt )
end

function lovr.draw( pass )
	app.draw(pass)
end
