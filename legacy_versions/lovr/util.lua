module('util',package.seeall)

_G.ffi = require 'ffi'
_G.glfw = ffi.os == 'Windows' and ffi.load('glfw3') or ffi.C
_M.glfw=_G.glfw

string.buffer = require('string.buffer')

ffi.cdef( [[
	enum {
		GLFW_RESIZABLE = 0x00020003,
		GLFW_VISIBLE = 0x00020004,
		GLFW_DECORATED = 0x00020005,
		GLFW_FLOATING = 0x00020007
	};

	typedef struct GLFWvidmode {
		int width;
		int height;
		int refreshRate;
	} GLFWvidmode;

	typedef struct GLFWwindow GLFWwindow;
	GLFWwindow* os_get_glfw_window(void);
	void glfwGetWindowPos(GLFWwindow* window, int *xpos, int *ypos);
	void glfwSetInputMode(GLFWwindow * window, int GLFW_CURSOR, int GLFW_CURSOR_HIDDEN);
	void glfwGetCursorPos(GLFWwindow *window, double *xpos, double *ypos); 	
]] )
GLFW_CURSOR        = 0x00033001
GLFW_CURSOR_HIDDEN = 0x00034002

function string.split( input )
	local stripped = input:gsub( '[\r\n,]', '' ) -- Remove newlines and commas
	local characters = {}

	for char in stripped:gmatch( '.' ) do
		table.insert( characters, char )
	end

	return characters
end

local mx = ffi.new( 'double[1]' )
local my = ffi.new( 'double[1]' )
function GetMouse()

	glfw.glfwGetCursorPos( game_handle, mx, my )
	return mx[ 0 ],my[ 0 ]

	
end

return _M