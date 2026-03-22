import random

from fuzzer.grammars.antlr.ip.ipVisitor import ipVisitor


class ipGenerator(ipVisitor):
    """
    Generates random IP expressions based on the ip.g4 grammar
    Modes:
        'cidrize': Full range of expressions (CIDR, ranges, brackets, wildcards).
        'parser': Only standard IPv4 and IPv6 addresses.
    """

    def __init__(self, mode: str = "cidrize"):
        super().__init__()
        if mode not in ("cidrize", "parser"):
            raise ValueError("mode must be 'cidrize' or 'parser'")
        self.mode = mode

    def generate(self):
        """Entry point to generate a single random valid IP expression."""
        return self.visitIpExpression(None)

    def visitIpExpression(self, ctx=None):
        """Orchestrates between IPv4 and IPv6."""
        if self.mode == "parser":
            return (
                self.visitIpv4Address(None)
                if random.random() < 0.5
                else self.visitIpv6Address(None)
            )
        else:
            return (
                self.visitIpv4Expression(None)
                if random.random() < 0.5
                else self.visitIpv6Expression(None)
            )

    # IPv4
    def visitIpv4Expression(self, ctx=None):
        """Generates IPv4 forms: CIDR, ranges, brackets, wildcards."""
        if self.mode == "parser":
            return self.visitIpv4Address(None)

        alt = random.randint(0, 6)

        if alt == 0:  # CIDR: a.b.c.d/prefix
            return f"{self.visitIpv4Address(None)}/{self.visitPrefixV4(None)}"

        elif alt == 1:  # Full hyphen range: a.b.c.d-w.x.y.z
            v1, v2 = sorted([self._random_ipv4_int() for _ in range(2)])
            return f"{self._int_to_ipv4(v1)}-{self._int_to_ipv4(v2)}"

        elif alt == 2:  # Shorthand hyphen: a.b.c.d-z
            prefix = [random.randint(0, 255) for _ in range(3)]
            o1, o2 = sorted([random.randint(0, 255) for _ in range(2)])
            return f"{prefix[0]}.{prefix[1]}.{prefix[2]}.{o1}-{o2}"

        elif alt == 3:  # Bracket form 1: 192.0.2.8[0-5]
            prefix = ".".join(str(random.randint(0, 255)) for _ in range(3))
            lo = random.randint(0, 255)
            hi = random.randint(lo, 255)
            fragment = self._range_to_octet_fragment(lo, hi)
            return f"{prefix}.{fragment}"

        elif alt == 4:  # Bracket form 2: 192.0.2.[0-5] / 192.0.2.[1234]
            prefix = ".".join(str(random.randint(0, 255)) for _ in range(3))
            return f"{prefix}.[{self.visitBracketContent(None)}]"

        elif alt == 5:  # Wildcard: a.b.c.*
            prefix = ".".join(str(random.randint(0, 255)) for _ in range(3))
            return f"{prefix}.*"

        else:  # Lone IP (Host Route)
            return self.visitIpv4Address(None)

    def visitIpv4Address(self, ctx=None):
        """Generates a standard 4-octet IPv4 address."""
        return self._int_to_ipv4(self._random_ipv4_int())

    def visitPrefixV4(self, ctx=None):
        """Generates IPv4 prefix 0-32 ."""
        return str(random.randint(0, 32))

    def visitBracketContent(self, ctx=None):
        if random.random() < 0.6:
            lo = random.randint(0, 255)
            hi = random.randint(lo, 255)
            return f"{lo}-{hi}"
        else:
            values = sorted(
                set(random.randint(0, 255) for _ in range(random.randint(1, 4)))
            )
            return "".join(str(v) for v in values)

    # IPv6
    def visitIpv6Expression(self, ctx=None):
        """Generates IPv6 forms: CIDR, range, lone IP ."""
        if self.mode == "parser":
            return self.visitIpv6Address(None)

        alt = random.randint(0, 2)
        if alt == 0:  # CIDR: ipv6/prefix
            return f"{self.visitIpv6Address(None)}/{self.visitPrefixV6(None)}"
        elif alt == 1:  # Full range: ipv6-ipv6
            v1, v2 = sorted([random.getrandbits(128) for _ in range(2)])
            return f"{self._int_to_ipv6(v1)}-{self._int_to_ipv6(v2)}"
        else:  # Lone IP
            return self.visitIpv6Address(None)

    def visitIpv6Address(self, ctx=None):
        """Generates IPv6 (full, compressed, or dual-stack/IPv4-mapped) ."""
        rand_val = random.random()

        # Dual-stack :
        if rand_val < 0.35:
            prefix = "::ffff:" if random.random() < 0.5 else "::"
            return f"{prefix}{self.visitIpv4Address(None)}"

        # Standard IPv6 (Full or Compressed)
        val = random.getrandbits(128)
        return self._int_to_ipv6(val)

    def visitIpv6WithEmbeddedIpv4(self):
        ipv4 = self.visitIpv4Address(None)
        # Number of hextets BEFORE IPv4 (0 to 6)
        n = random.randint(0, 6)
        hextets = [self._random_hextet() for _ in range(n)]
        use_compression = random.random() < 0.5 and n < 6
        if use_compression:
            # position where :: is inserted
            pos = random.randint(0, len(hextets))
            left = hextets[:pos]
            right = hextets[pos:]
            if left and right:
                prefix = ":".join(left) + "::" + ":".join(right)
            elif left:
                prefix = ":".join(left) + "::"
            elif right:
                prefix = "::" + ":".join(right)
            else:
                prefix = "::"
        else:
            prefix = ":".join(hextets)
        # Combine with IPv4
        if prefix == "":
            return ipv4  # edge (rare, but safe)
        elif prefix.endswith(":") or prefix.endswith("::"):
            return f"{prefix}{ipv4}"
        else:
            return f"{prefix}:{ipv4}"

    def visitPrefixV6(self, ctx=None):
        """Generates IPv6 prefix 0-128 ."""
        return str(random.randint(0, 128))

    # Helpers
    def _random_ipv4_int(self):
        """Generates a random 32-bit integer."""
        return random.randint(0, 0xFFFFFFFF)

    def _int_to_ipv4(self, val):
        """Converts a 32-bit integer to a dotted-quad string."""
        return f"{(val >> 24) & 0xFF}.{(val >> 16) & 0xFF}.{(val >> 8) & 0xFF}.{val & 0xFF}"

    def _int_to_ipv6(self, val):
        """Converts a 128-bit integer to compressed IPv6 string."""
        hextets = [(val >> (16 * (7 - i))) & 0xFFFF for i in range(8)]
        parts = [format(h, "x") for h in hextets]
        best_start = -1
        best_len = 0
        i = 0
        while i < 8:
            if hextets[i] == 0:
                j = i
                while j < 8 and hextets[j] == 0:
                    j += 1
                length = j - i
                if length > best_len and length > 1:  # must be >= 2
                    best_start = i
                    best_len = length
                i = j
            else:
                i += 1
        if best_len > 1:
            left = parts[:best_start]
            right = parts[best_start + best_len :]

            if left and right:
                return ":".join(left) + "::" + ":".join(right)
            elif left:  # trailing zeros
                return ":".join(left) + "::"
            elif right:  # leading zeros
                return "::" + ":".join(right)
            else:  # all zeros
                return "::"
        return ":".join(parts)

    def _range_to_octet_fragment(self, lo: int, hi: int) -> str:
        """
        Convert a numeric range into a bracket-style octet fragment when possible.
        Examples:
        80-85   -> 8[0-5]
        250-255 -> 25[0-5]
        12-19   -> [12-19]
        """
        s1, s2 = str(lo), str(hi)
        if len(s1) == len(s2) and s1[:-1] == s2[:-1]:
            return f"{s1[:-1]}[{s1[-1]}-{s2[-1]}]"
        return f"[{lo}-{hi}]"

    def _random_hextet(self):
        return format(random.randint(0, 0xFFFF), "x")


if __name__ == "__main__":
    gen = ipGenerator(mode="cidrize")
    for i in range(15):
        print(f"Cidrize Sample {i + 1}: {gen.generate()}")

    gen2 = ipGenerator(mode="parser")
    for i in range(15):
        print(f"Parser Sample {i + 1}: {gen2.generate()}")
