import re
class AddressParser:
    @staticmethod
    def normalize_address(addr):
        addr = str(addr).lower()
        addr = re.sub(r"[^a-z0-9\s]", "", addr)
        return " ".join(addr.split())
