local serial_left = 'LHR-C6E6E6A8'
local serial_right = 'LHR-168E5F19'
--local serial_bs1 = 'LHB-22D049A2'
--local serial_bs2 = 'LHB-7C823E1C'
local config

config = {
    addr = false,
    port = false,
    trackings = {
        {serial_left, '/avatar/parameters/petting_volume'},
        {serial_right, '/avatar/parameters/petting_volume_r'}
    },
    getBySerial = function(serial)
        for _, trackable in pairs(config.trackings) do
            if serial == trackable[1] then return trackable end
        end
    end
}

return config