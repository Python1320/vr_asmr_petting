local util = require "util"
local io = require "io"
--local sock = require'sock'
local ffi = require'ffi'

local ps,err = assert(require'petting-system','petting-system module did not load')

local game_pass 
local app = {}
function app.load()
	
	game_pass = lovr.graphics.newPass(  )
	lovr.graphics.setBackgroundColor( 0, 0, 0 )
  
	--game_handle = ffi.C.os_get_glfw_window()
	--glfw.glfwSetInputMode( game_handle, GLFW_CURSOR, GLFW_CURSOR_HIDDEN )
	math.randomseed( os.time() )
	ps.start()
end


local debug_state = {}
function app.update( dt )
	ps.update(dt, debug_state )
end

-- Set the units of the default font to pixels instead of meters
local font = lovr.graphics.getDefaultFont()
font:setPixelDensity(3)

-- Set up a 2D orthographic projection, where (0, 0) is the upper
-- left of the window and the units are in pixels
local width, height = lovr.system.getWindowDimensions()
local projection = Mat4():orthographic(0, width, 0, height, -10, 10)

function app.draw(pass)
  pass:setViewPose(1, mat4():identity())
  pass:setProjection(1, projection)
  pass:setDepthTest()
--[[
  local button = { x = width / 2, y = height / 2, w = 180, h = 60 }

  local mx, my = lovr.system.getMousePosition()
  local pressed = lovr.system.isMouseDown(1)
  local hovered = mx > button.x - button.w / 2 and mx < button.x + button.w / 2 and
                  my > button.y - button.h / 2 and my < button.y + button.h / 2

  if hovered and pressed then
    pass:setColor(.25, .25, .27)
  elseif hovered then
    pass:setColor(.20, .20, .22)
  else
    pass:setColor(.15, .15, .17)
  end

  pass:plane(button.x, button.y, 0, button.w, button.h)
--]]

  pass:setColor(1, 1, 1)
  local i=0
  for k,v in pairs(debug_state) do
    i=i+1
    local n=tonumber(v)
    if n then
      pass:text(tostring(k), width*0.5,64*i, 0)
      pass:setColor(0.3,0.3,0.3)        
      pass:plane(width*.5, i*64-16-2, 0, 
                  256, 16)
      pass:setColor(1, 1, 1)   
      pass:plane(width*.5, i*64-16-2, 0, 
                  256*n, 16)

    else
    
      pass:text(tostring(k)..": "..tostring(v), width*0.5,64*i, 0)
    end
  end
end


return app
