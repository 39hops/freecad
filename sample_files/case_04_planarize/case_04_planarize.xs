# Feature layer, blanket dielectric, then planarized cap.
depth(100.0)
height(100.0)
delta(1 * dbu)

substrate = bulk
m1 = layer("2/0")
i1 = layer("3/0")

m1_t = 1
i1_t = 1
zero_bias = 0

m1_dep = deposit(m1_t)
mask(m1.inverted).etch(m1_t, :taper => 45, :bias => zero_bias, :into => m1_dep)

i1_dep = deposit(i1_t)
i1_dep = deposit(i1_t)
planarize(:into => planar_top, :less => 3)

output("2/0", m1_dep)
output("3/0", i1_dep)
