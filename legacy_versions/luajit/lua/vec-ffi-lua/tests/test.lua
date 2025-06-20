#!/usr/bin/env luajit
local ffi = require 'ffi'
require 'vec-ffi'
assert(ffi.sizeof'vec3b_t' == 3)
