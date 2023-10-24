import re

class UrlGenerator:
    @staticmethod
    def generate_ith(url_like : str, i : int):

        # Capture episode number
        regex = "\_Ep\_(\d+)\_"

        match = re.search(regex, url_like)
        if match is None:
            raise Exception("Errore durante il parsing dell'url")

        raw = match.group(1)

        # Create a numerical string with len(raw) leading zeros
        ith_raw = str(i).zfill(len(raw))
        return re.sub(regex, f'_Ep_{ith_raw}_', url_like)