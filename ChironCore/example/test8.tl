:x = 100
:y = 200
if :x > 50 [
    :x = 10
    if :y > 100 [
        :y = 20
        :x = :y + 5
    ] else [
        :y = 30
    ]
    :z = :x + :y
] else [
    :z = :x
]
:w = :z + :x
