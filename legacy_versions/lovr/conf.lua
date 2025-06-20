lovr.filesystem.setRequirePath([[lua/?/init.lua;lua/?.lua;]] .. lovr.filesystem.getRequirePath())


print("Loading: conf.lua")
function lovr.conf(t)
	print("Loading: lovr.conf()")
	-- comment for VR
	t.headset.drivers = { 'desktop' }
	t.identity = "vrpets"
	t.modules.headset = false
	t.window.title = 'VRPets'
	--t.window.icon = 'assets/application.png'
	
	t.window.width = 800
	t.window.height = 600
end


