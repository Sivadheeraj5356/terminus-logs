"""Implement the public INC-8821 adjudication contracts in this module."""

import hashlib
import policy_graph


def main():
    """Derive every profile output from the public evidence and authority rules.

    policy_graph only exposes public authority-ordering vocabulary. It is not
    an adjudication implementation or a substitute for the contracts.
    """
    _ = (hashlib.sha256, policy_graph.authority_rank)
    raise NotImplementedError("implement the public adjudication contracts")


if __name__ == "__main__":
    main()
