module('sender',package.seeall)

local losc = require'losc'
local plugin = require'losc.plugins.udp-sock'

local udp = plugin.new{
	sendAddr = require'config'.sendAddr or '127.0.0.1',
	sendPort = require'config'.sendPort or 9000,
	recvAddr = require'config'.recvAddr or '*',
	recvPort = require'config'.recvPort or 9123,
}

local osc = losc.new{
	plugin = udp
}

function startReceiving()

	local function print_data(data)
		local msg = data.message
		print('address: ' .. msg.address, 'timestamp: ' .. data.timestamp)
		for index, argument in ipairs(msg) do
			print('index: ' .. index, 'arg: ' .. argument)
		end
	end
		
	osc:add_handler('/test', function(data)
		print_data(data)
	end)

	osc:open()
end

function sendMessage(payload)
        
    local message = losc.new_message(payload)
    

    return osc:send(message)
end
return _M