import os
m = 643.6
size(m,m)

s = 347    # size of the center square
r = 240    # outside circle    
rs = 98    # inside circle, "hole"
x = width()*.5-s*.5
y = height()*.5-s*.5

b = BezierPath()
b.rect(x, y, s, s)
b.oval(x-.5*r,y-.5*r, r, r)
b.oval(x-.5*r,y+s-.5*r, r, r)
b.oval(x+s-.5*r,y-.5*r, r, r)
b.oval(x+s-.5*r,y+s-.5*r, r, r)
b.removeOverlap()


holes = BezierPath()
holes.oval(x-.5*rs,y-.5*rs, rs, rs)
holes.oval(x-.5*rs,y+s-.5*rs, rs, rs)
holes.oval(x+s-.5*rs,y-.5*rs, rs, rs)
#holes.oval(x+s-.5*rs,y+s-.5*rs, rs, rs)
#holes.oval(x+.5*s-.5*rs, y+.5*s-.5*rs, rs, rs )

#p = b.xor(holes)

# gradient locations
#s1 = (width()*.55, height()) 
#s2 = (width()*0.15, 0)


addName = False

rgb1 = (0.0, 0.7, 1.0)
rgb2 = (0.0, 0.8, 0.2)

versions = [
    ('_store', (0.0, 0.6, 1.0), (0.9, 0.7, 0.0), 45),
    ('_develop', (0.81, 0.79, 0.83), (0.8, 0.9, 1.07), 45),
    ('_student', (0.44, 0.02, 0.9), (0.17, 0.9, 0.97), 45),
    ('_trial', (1.2, 0.1, 0.57), (1.0, 0.8, 0.2), 45),
    ('_expired', (0.88, 0.88, .88), (0.98, 0.98, 0.99), 45),
    ]


#resourcesPath = "/Users/erik/code/superpolator/source/resources"
resourcesPath = "/Users/erik/code/sp5/source/resources"
#resourcesPath = os.path.join(os.path.dirname(os.getcwd()), 'extension', 'resources')

mechanicIconPath = "/Users/erik/code/longboard"

for tag, rgb1, rgb2, angle in versions:
    
    aa = angle
    a1 = radians(aa)
    a2 = radians(aa)+pi
    r = width() * 1
    c = width()*.5, height()*.5
    s1 = c[0] + sin(a1)*r, c[1] + cos(a1)*r
    s2 = c[0] + sin(a2)*r, c[1] + cos(a2)*r

    gradientData = (s1,
        s2,
        [rgb1, rgb2],  # colors
        [.66, .33]   )
    linearGradient(*gradientData)
    print(tag, "linearGradient", gradientData)
    drawPath(b)
    fill(1,1,1,0.9)
    drawPath(holes)

    namePath = BezierPath()
    if addName:
        nx = 219
        fill(1,1,1,0.98)
        fontSize(58)
        font("ActionCondBold-Grade3")
        namePath.text("Superpolator", (nx, 303), font="ActionCondBold-Grade2", fontSize=73)
        #fontSize(17.4)
        #font("ActionText-MediumDark")
        #namePath.text("Designspaces for Robofont", (nx, 282), font="ActionText-MediumDark", fontSize=14.5)

    drawPath(namePath)

    if addName:
        ext = "_name"
    else:
        ext = ""
    saveImage(os.path.join(resourcesPath, f"superpolatorExtensionIcon{ext}{tag}.png"))
    
    #saveImage(os.path.join(resourcesPath, f"superpolator_icon_512{ext}{tag}.pdf"))

    print('mechanicIconPath', mechanicIconPath)
    saveImage(os.path.join(mechanicIconPath, f"superpolatorMechanicIcon_512{ext}{tag}.png"))
    
    