module("util", package.seeall)
local ffi = require'ffi'
ffi.cdef[[
void Sleep(int ms);
int poll(struct pollfd *fds, unsigned long nfds, int timeout);
]]
local sleep

if ffi.os == "Windows" then
    function _M.sleep(s)
        ffi.C.Sleep(s * 1000)
    end
else
    function _M.sleep(s)
        ffi.C.poll(nil, 0, s * 1000)
    end
end

function table.count(t)
    local c = 0

    for k, v in pairs(t) do
        c = c + 1
    end

    return c
end

return _M