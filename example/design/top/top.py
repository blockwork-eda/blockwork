from blockwork.build import Entity

@Entity.register()
class Top(Entity):
    files = [Entity.ROOT / "adder.sv",
             Entity.ROOT / "counter.sv",
             Entity.ROOT / "top.sv.mako"]
