:a = 0
:b = 1
:n = 5
repeat :n [
    :temp = :a + :b
    :a = :b
    :b = :temp
    forward :a
]
:result = :a
