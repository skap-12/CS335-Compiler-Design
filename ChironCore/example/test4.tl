:x = 1
:y = 2
if :x < 10 [
    :x = :x + 1
    if :y > 0 [
        :z = :x + :y
    ] else [
        :z = :x - :y
    ]
] else [
    :z = 0
]
:final = :z
