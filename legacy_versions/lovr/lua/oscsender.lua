module('sender',package.seeall)

local losc = require'losc'
local plugin = require'losc.plugins.udp-ljsocket'

local udp = plugin.new{
	sendAddr = require'config'.sendAddr or '127.0.0.1',
	sendPort = require'config'.sendPort or 9000,
	recvAddr = require'config'.recvAddr or '0.0.0.0',
	recvPort = require'config'.recvPort or 9123,
}

local osc = losc.new{
	plugin = udp
}

function start_receiver()

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

  return coroutine.create(function()
      local ok,err = osc:open()
      if not ok then
        error(err or "osc:open")
      end
  end)
end

function send(payload)
        
    local message = losc.new_message(payload)
    

    return osc:send(message)
end
return _M