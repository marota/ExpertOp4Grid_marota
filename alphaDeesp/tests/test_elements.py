"""Unit tests for the substation element model
(:mod:`alphaDeesp.core.elements`): Production, Consumption, OriginLine,
ExtremityLine — the value objects the ``Simulation`` backends emit and that
``AlphaDeesp`` consumes to enumerate busbar configurations."""

from alphaDeesp.core.elements import (
    Consumption,
    ExtremityLine,
    OriginLine,
    Production,
)


class TestProduction:
    def test_fields_and_busbar_property(self):
        p = Production(busbar_id=0, value=3.5)
        assert p.busbar_id == 0
        assert p.busbar == 0
        assert p.value == 3.5

    def test_busbar_setter(self):
        p = Production(busbar_id=0)
        p.busbar = 1
        assert p.busbar_id == 1

    def test_ids_increment_monotonically(self):
        a = Production(0)
        b = Production(0)
        assert b.ID == a.ID + 1

    def test_repr_mentions_type_and_value(self):
        r = repr(Production(0, 3.5))
        assert "PRODUCTION" in r and "3.5" in r


class TestConsumption:
    def test_fields_and_busbar_setter(self):
        c = Consumption(busbar_id=1, value=4.0)
        assert c.busbar == 1 and c.value == 4.0
        c.busbar = 0
        assert c.busbar_id == 0

    def test_repr_mentions_type(self):
        assert "CONSUMPTION" in repr(Consumption(0, 4.0))


class TestOriginLine:
    def test_fields(self):
        line = OriginLine(busbar_id=0, end_substation_id=5, flow_value=[42.0])
        assert line.busbar == 0
        assert line.end_substation_id == 5
        assert line.flow_value == [42.0]

    def test_busbar_setter_and_repr(self):
        line = OriginLine(0, end_substation_id=5, flow_value=[1.0])
        line.busbar = 1
        assert line.busbar_id == 1
        assert "ORIGINLINE" in repr(line)


class TestExtremityLine:
    def test_fields(self):
        line = ExtremityLine(busbar_id=1, start_substation_id=3, flow_value=[-7.0])
        assert line.busbar == 1
        assert line.start_substation_id == 3
        assert line.flow_value == [-7.0]

    def test_repr_mentions_type(self):
        assert "EXTREMITYLINE" in repr(
            ExtremityLine(0, start_substation_id=3, flow_value=[1.0]))
