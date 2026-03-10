:dist = 10
:angle = 45
:flag = 1
repeat 3 [
    forward :dist
    if :flag == 1 [
        right :angle
        :dist = :dist * 2
        :flag = 0
    ] else [
        left :angle
        :dist = :dist / 2
        :flag = 1
    ]
]
:final = :dist
