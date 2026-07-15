class EmailProviderError(Exception):
    pass


class EmailProvider:
    def send(self, to_email, template, payload):
        attempt = payload.get("_attempt", 1)
        fail_until_attempt = payload.get("fail_until_attempt", 0)
        if attempt <= fail_until_attempt:
            raise EmailProviderError(f"intentional demo failure on attempt {attempt}")

        return f"local-{to_email}-{template}"
