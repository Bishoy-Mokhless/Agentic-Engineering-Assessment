"""Adapters for external data providers (Eurostat, World Bank) and the HR source files.

Spring analogy: Feign clients / RestTemplate wrappers. One module per provider, so a
provider change (e.g. a dataset being discontinued, D-25) only touches one file.
"""
