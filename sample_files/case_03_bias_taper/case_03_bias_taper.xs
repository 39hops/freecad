# Exercises opposite bias directions and different taper angles.
depth(100.0)
height(100.0)
delta(1 * dbu)

substrate = bulk
wide = layer("2/0")
narrow = layer("3/0")

wide_t = 1
narrow_t = 1
wide_bias = -1
narrow_bias = 1

wide_dep = deposit(wide_t)
mask(wide.inverted).etch(wide_t, :taper => 35, :bias => wide_bias, :into => wide_dep)

narrow_dep = deposit(narrow_t)
mask(narrow.inverted).etch(narrow_t, :taper => 60, :bias => narrow_bias, :into => narrow_dep)

output("2/0", wide_dep)
output("3/0", narrow_dep)
