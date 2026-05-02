# Basic two-layer stack with no vias.
depth(100.0)
height(100.0)
delta(1 * dbu)

substrate = bulk
m1 = layer("2/0")
m2 = layer("3/0")

m1_t = 1
m2_t = 1
m1_bias = 0
m2_bias = 0

m1_dep = deposit(m1_t)
mask(m1.inverted).etch(m1_t, :taper => 45, :bias => m1_bias, :into => m1_dep)

m2_dep = deposit(m2_t)
mask(m2.inverted).etch(m2_t, :taper => 45, :bias => m2_bias, :into => m2_dep)

output("2/0", m1_dep)
output("3/0", m2_dep)
