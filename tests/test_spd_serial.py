"""Tests for factory-model SPD assembly serial generation."""

from __future__ import annotations

import datetime

import pytest

from spd_serial import (
    MICRON_BATCH_STEP,
    build_module_unique_id,
    generate_spd_serials,
    resolve_serial_scheme,
)


class TestResolveSerialScheme:
    def test_gskill_always_blank(self):
        assert resolve_serial_scheme("gskill", ["xmp"]) == ("empty", 0)

    def test_corsair_jedec_blank(self):
        assert resolve_serial_scheme("corsair", ["jedec"]) == ("empty", 0)

    def test_corsair_ddr4_xmp_programmed(self):
        assert resolve_serial_scheme("corsair", ["xmp"], 4) == ("binary_le", 1)

    def test_corsair_ddr5_xmp_blank(self):
        assert resolve_serial_scheme("corsair", ["xmp"], 5) == ("empty", 0)
        assert resolve_serial_scheme("corsair", ["both"], 5) == ("empty", 0)

    def test_uses_null_spd_serial(self):
        from spd_serial import uses_null_spd_serial

        assert uses_null_spd_serial("gskill", ["xmp"], 5)
        assert uses_null_spd_serial("corsair", ["xmp"], 5)
        assert not uses_null_spd_serial("kingston", ["xmp"], 5)
        assert uses_null_spd_serial("corsair", ["jedec"], 4)
        assert not uses_null_spd_serial("corsair", ["xmp"], 4)

    def test_kingston_big_endian(self):
        assert resolve_serial_scheme("kingston", ["xmp"]) == ("binary_be", 1)

    def test_crucial_micron_batch_step(self):
        assert resolve_serial_scheme("crucial", ["xmp"]) == ("binary_be", MICRON_BATCH_STEP)
        assert resolve_serial_scheme("micron", ["jedec"]) == ("binary_be", MICRON_BATCH_STEP)

    def test_teamgroup_tester_format(self):
        assert resolve_serial_scheme("teamgroup", ["xmp"]) == ("tester_seq_le", 1)


class TestGenerateSpdSerials:
    def test_gskill_all_zeros(self):
        serials = generate_spd_serials(
            "gskill",
            "F5-6000J3040F16GX2-TZ5RK",
            5,
            2,
            serial_salt=12345,
            profiles=["xmp"],
            verified="2026-08-12",
        )
        assert len(serials) == 2
        assert serials[0].serial_number == "0x00000000"
        assert serials[1].serial_number == "0x00000000"
        assert serials[0].encoding == "empty"

    def test_corsair_jedec_blank(self):
        serials = generate_spd_serials(
            "corsair",
            "CMK16GX4M1A2400C16",
            4,
            1,
            profiles=["jedec"],
        )
        assert serials[0].serial_number == "0x00000000"

    def test_corsair_ddr4_xmp_sequential_le(self):
        serials = generate_spd_serials(
            "corsair",
            "CMK32GX4M2B3200C16",
            4,
            2,
            serial_salt=42,
            profiles=["xmp"],
        )
        assert serials[0].encoding == "binary_le"
        assert serials[1].uint32_le == serials[0].uint32_le + 1

    def test_corsair_ddr5_thp_dump_skus_blank(self):
        thp_parts = [
            "CMH32GX5M2B6400C32",
            "CMH32GX5M2B6400C36",
            "CMH32GX5M2D6000C36",
            "CMH32GX5M2E6000C36",
            "CMH32GX5M2X7200C34",
            "CMH64GX5M2B6000Z30",
            "CMK32GX5M2B5600C36",
            "CMK32GX5M2B6600C38",
            "CMK32GX5M2D6000Z36",
            "CMK64GX5M2B5600C40",
            "CMK64GX5M2B6400C32",
            "CMK64GX5M2B6600C32",
            "CMT32GX5M2X7200C34",
            "CMT32GX5M2X7600C36",
        ]
        for part in thp_parts:
            serials = generate_spd_serials(
                "corsair",
                part,
                5,
                2,
                serial_salt=12345,
                profiles=["xmp"],
            )
            assert serials[0].serial_number == "0x00000000"
            assert serials[1].serial_number == "0x00000000"
            assert serials[0].encoding == "empty"

    def test_kingston_be_sequential(self):
        serials = generate_spd_serials(
            "kingston",
            "KF564C32BBEK2-32",
            5,
            2,
            serial_salt=99,
            profiles=["both"],
        )
        assert serials[0].encoding == "binary_be"
        assert serials[1].uint32_be == serials[0].uint32_be + 1

    def test_crucial_batch_step_1105(self):
        serials = generate_spd_serials(
            "crucial",
            "CT2K16G56C46U5",
            5,
            2,
            serial_salt=7,
            profiles=["expo"],
        )
        assert serials[0].encoding == "binary_be_batch"
        assert serials[1].uint32_be == serials[0].uint32_be + MICRON_BATCH_STEP

    def test_teamgroup_tester_byte(self):
        serials = generate_spd_serials(
            "teamgroup",
            "FF3D532G6400HC32ADC01",
            5,
            2,
            serial_salt=0x1200,
            profiles=["xmp"],
        )
        assert serials[0].raw_bytes[0] == serials[1].raw_bytes[0]
        assert serials[0].raw_bytes[0] != 0
        assert serials[1].uint32_le > serials[0].uint32_le

    def test_serial_salt_changes_lot(self):
        a = generate_spd_serials(
            "corsair",
            "CMK32GX4M2B3200C16",
            4,
            1,
            serial_salt=1,
            profiles=["xmp"],
        )
        b = generate_spd_serials(
            "corsair",
            "CMK32GX4M2B3200C16",
            4,
            1,
            serial_salt=2,
            profiles=["xmp"],
        )
        assert a[0].serial_number != b[0].serial_number

    def test_module_unique_id_uses_verified_date(self):
        verified = "2026-08-12"
        serials = generate_spd_serials(
            "gskill",
            "F5-6000J3040F16GX2-TZ5RK",
            5,
            1,
            profiles=["xmp"],
            verified=verified,
        )
        when = datetime.date.fromisoformat(verified)
        expected = build_module_unique_id("gskill", serials[0].raw_bytes, when)
        assert serials[0].module_unique_id == expected

    def test_same_salt_same_part_same_serials(self):
        kwargs = dict(
            brand="corsair",
            part_number="CMK32GX4M2B3200C16",
            generation=4,
            stick_count=2,
            serial_salt=999,
            profiles=["xmp"],
        )
        first = generate_spd_serials(**kwargs)
        second = generate_spd_serials(**kwargs)
        assert [s.serial_number for s in first] == [s.serial_number for s in second]
