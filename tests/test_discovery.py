"""Tests for multi-tier ArcGIS endpoint discovery.

Covers the new Tier 1b (alternate domain probing) and Tier 1.75 (Hub search)
functionality, plus the existing Tier 1 and Tier 1.5 tiers.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import gov_arcgis_scanner as scanner


# ---------------------------------------------------------------------------
# Tier 1b — Alternate Domain Generation
# ---------------------------------------------------------------------------

class TestGenerateAlternateDomains:
    """Tests for _generate_alternate_domains()."""

    def test_contra_costa_county(self):
        """Contra Costa County should produce 'cccounty' variant domains."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        # Must include the cccounty.us domain (the real-world answer)
        assert any("cccounty" in d for d in domains)
        # Must include legacy co. pattern
        assert any(d.startswith("co.") for d in domains)

    def test_county_abbreviation_initials(self):
        """County names should produce initials+county domains."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County", ""
        )
        # "cc" initials + "county" suffix
        assert "cccounty.us" in domains
        assert "cccounty.gov" in domains

    def test_city_abbreviation(self):
        """City names should produce cityof+name domains."""
        domains = scanner._generate_alternate_domains(
            "City of Las Vegas", ""
        )
        assert any("cityoflasvegas" in d for d in domains)
        assert any("lasvegas" in d for d in domains)

    def test_homepage_domain_excluded(self):
        """The homepage domain itself should not appear in candidates."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        assert "contracosta.ca.gov" not in domains

    def test_empty_name(self):
        """Empty jurisdiction name returns empty list."""
        assert scanner._generate_alternate_domains("", "") == []

    def test_single_word_county(self):
        """Single-word county name like 'Lake County'."""
        domains = scanner._generate_alternate_domains(
            "Lake County",
            "https://www.lakecountyca.gov",
        )
        # Should include "lakecounty.us" etc.
        assert any("lakecounty" in d for d in domains)

    def test_legacy_co_pattern_with_state(self):
        """Legacy co.{name}.{state}.us pattern generated when state available."""
        # Homepage is the main .gov site; GIS is on the legacy co.name.state.us domain
        domains = scanner._generate_alternate_domains(
            "Surry County",
            "https://www.surrync.gov",
        )
        # _extract_state_from_url won't find "nc" in "surrync.gov", so provide
        # a domain with the state code explicitly in a part
        domains2 = scanner._generate_alternate_domains(
            "Surry County",
            "https://surry.nc.gov",
        )
        assert "co.surry.nc.us" in domains2

    def test_no_duplicate_domains(self):
        """Generated list should have no duplicates."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        assert len(domains) == len(set(d.lower() for d in domains))

    def test_multi_word_county_legacy_pattern(self):
        """Multi-word county name should generate both full and first-word legacy patterns."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        # Full concat: co.contracosta.ca.us
        assert "co.contracosta.ca.us" in domains
        # First word: co.contra.ca.us
        assert "co.contra.ca.us" in domains


class TestExtractStateFromUrl:
    """Tests for _extract_state_from_url()."""

    def test_ca_gov(self):
        assert scanner._extract_state_from_url("https://contracosta.ca.gov") == "ca"

    def test_nc_us(self):
        assert scanner._extract_state_from_url("https://co.surry.nc.us") == "nc"

    def test_no_state(self):
        assert scanner._extract_state_from_url("https://example.com") == ""

    def test_empty_url(self):
        assert scanner._extract_state_from_url("") == ""

    def test_gov_not_state(self):
        """'gov' is 3 chars, should not match as state."""
        assert scanner._extract_state_from_url("https://example.gov") == ""

    def test_us_not_state(self):
        """'us' is a TLD, should not match as state (not in _US_STATES)."""
        # "us" is not a US state abbreviation
        result = scanner._extract_state_from_url("https://example.us")
        assert result == ""


# ---------------------------------------------------------------------------
# Tier 1b — Alternate Domain Probing
# ---------------------------------------------------------------------------

class TestProbeAlternateDomains:
    """Tests for _probe_alternate_domains() with mocked HTTP."""

    @patch.object(scanner, "fetch")
    @patch.object(scanner, "is_safe_url", return_value=True)
    def test_finds_valid_endpoint(self, mock_safe, mock_fetch):
        """Should return URL when a valid ArcGIS endpoint responds."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"services": [{"name": "Zoning"}], "folders": []}

        # Return None for most, valid response for gis.cccounty.us
        def side_effect(url, timeout=8):
            if "gis.cccounty.us" in url:
                return mock_resp
            return None

        mock_fetch.side_effect = side_effect

        results = scanner._probe_alternate_domains(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        assert any("gis.cccounty.us" in u for u in results)

    @patch.object(scanner, "fetch", return_value=None)
    @patch.object(scanner, "is_safe_url", return_value=True)
    def test_returns_empty_when_no_match(self, mock_safe, mock_fetch):
        """Should return empty set when no endpoints respond."""
        results = scanner._probe_alternate_domains("Nonexistent County", "")
        assert results == set()

    @patch.object(scanner, "fetch")
    @patch.object(scanner, "is_safe_url", return_value=True)
    def test_skips_empty_services(self, mock_safe, mock_fetch):
        """Should skip endpoints that return 200 but have no services/folders."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # No "services" or "folders" keys
        mock_fetch.return_value = mock_resp

        results = scanner._probe_alternate_domains("Lake County", "")
        assert results == set()

    @patch.object(scanner, "fetch")
    def test_ssrf_protection(self, mock_fetch):
        """Should never fetch URLs that fail is_safe_url()."""
        # Make is_safe_url reject everything
        with patch.object(scanner, "is_safe_url", return_value=False):
            scanner._probe_alternate_domains("Test County", "")
        mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# Tier 1.75 — ArcGIS Hub Search
# ---------------------------------------------------------------------------

class TestSearchHubForJurisdiction:
    """Tests for _search_hub_for_jurisdiction() with mocked HTTP."""

    @patch.object(scanner.session, "get")
    def test_finds_hub_datasets(self, mock_get):
        """Should extract REST directory roots from Hub dataset URLs."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "name": "Contra Costa County Zoning",
                        "source": "Contra Costa County",
                        "organization": "cocogis",
                        "url": "https://gis.cccounty.us/arcgis/rest/services/CCMAP/CCMAP/MapServer/3",
                    }
                }
            ]
        }
        mock_get.return_value = mock_resp

        with patch.object(scanner, "is_safe_url", return_value=True):
            results = scanner._search_hub_for_jurisdiction("Contra Costa County")

        assert any("gis.cccounty.us" in u for u in results)

    @patch.object(scanner.session, "get")
    def test_filters_irrelevant_results(self, mock_get):
        """Should skip results that don't mention the jurisdiction."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "name": "Some Other County Zoning",
                        "source": "Other County",
                        "organization": "othergis",
                        "url": "https://other.example.com/arcgis/rest/services/Zoning/MapServer",
                    }
                }
            ]
        }
        mock_get.return_value = mock_resp

        with patch.object(scanner, "is_safe_url", return_value=True):
            results = scanner._search_hub_for_jurisdiction("Contra Costa County")

        assert results == set()

    @patch.object(scanner.session, "get")
    def test_handles_api_error(self, mock_get):
        """Should return empty set on API errors."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        results = scanner._search_hub_for_jurisdiction("Test County")
        assert results == set()

    @patch.object(scanner.session, "get")
    def test_handles_network_error(self, mock_get):
        """Should return empty set on network errors."""
        import requests
        mock_get.side_effect = requests.ConnectionError("Network unreachable")

        results = scanner._search_hub_for_jurisdiction("Test County")
        assert results == set()

    @patch.object(scanner.session, "get")
    def test_normalizes_to_rest_directory(self, mock_get):
        """Should normalize feature layer URLs to REST directory root."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "name": "Lake County Parcels",
                        "source": "Lake County",
                        "organization": "lakegis",
                        "url": "https://gis.lake.gov/arcgis/rest/services/Parcels/FeatureServer/0",
                    }
                }
            ]
        }
        mock_get.return_value = mock_resp

        with patch.object(scanner, "is_safe_url", return_value=True):
            results = scanner._search_hub_for_jurisdiction("Lake County")

        # Should be normalized to the root, not the specific layer
        assert results == {"https://gis.lake.gov/arcgis/rest/services"}


# ---------------------------------------------------------------------------
# Integration: Discovery Flow
# ---------------------------------------------------------------------------

class TestDiscoveryFlow:
    """Tests for the llm_search_for_arcgis() orchestration."""

    @patch.object(scanner, "guess_arcgis_urls", return_value=set())
    @patch.object(scanner, "_probe_alternate_domains",
                  return_value={"https://gis.cccounty.us/arcgis/rest/services"})
    @patch.object(scanner, "_search_agol_for_jurisdiction")
    def test_tier1b_short_circuits(self, mock_agol, mock_alt, mock_tier1):
        """If Tier 1b finds results, Tier 1.5+ should not be called."""
        result = scanner.llm_search_for_arcgis(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        assert "https://gis.cccounty.us/arcgis/rest/services" in result
        mock_agol.assert_not_called()

    @patch.object(scanner, "guess_arcgis_urls", return_value=set())
    @patch.object(scanner, "_probe_alternate_domains", return_value=set())
    @patch.object(scanner, "_search_agol_for_jurisdiction", return_value=set())
    @patch.object(scanner, "_search_hub_for_jurisdiction",
                  return_value={"https://gis.example.gov/arcgis/rest/services"})
    def test_tier175_after_agol_fails(self, mock_hub, mock_agol, mock_alt,
                                      mock_tier1):
        """Hub search (1.75) should run when Tier 1, 1b, and 1.5 all fail."""
        # Suppress Tier 2 by clearing API key
        with patch.object(scanner, "_ANTHROPIC_API_KEY", ""):
            result = scanner.llm_search_for_arcgis(
                "Test County",
                "https://test.gov",
            )
        assert "https://gis.example.gov/arcgis/rest/services" in result

    @patch.object(scanner, "guess_arcgis_urls",
                  return_value={"https://gis.test.gov/arcgis/rest/services"})
    @patch.object(scanner, "_probe_alternate_domains")
    def test_tier1_short_circuits_all(self, mock_alt, mock_tier1):
        """If Tier 1 finds results, no other tiers should run."""
        result = scanner.llm_search_for_arcgis("Test City", "https://test.gov")
        assert len(result) == 1
        mock_alt.assert_not_called()


# ---------------------------------------------------------------------------
# Security: URL validation in alternate domain probing
# ---------------------------------------------------------------------------

class TestAlternateDomainSecurity:
    """Security-focused tests for the alternate domain probing tier."""

    def test_generated_domains_are_simple(self):
        """Generated domains should not contain path components or special chars."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County",
            "https://contracosta.ca.gov",
        )
        for domain in domains:
            assert "/" not in domain, f"Domain contains path: {domain}"
            assert " " not in domain, f"Domain contains space: {domain}"
            assert "?" not in domain, f"Domain contains query: {domain}"
            assert "#" not in domain, f"Domain contains fragment: {domain}"
            assert "@" not in domain, f"Domain contains userinfo: {domain}"

    def test_prompt_injection_in_name_handled(self):
        """Jurisdiction name with special chars should be sanitised upstream."""
        # The name is sanitised by sanitize_jurisdiction_name() before reaching
        # our function, but let's verify our function handles weird input gracefully
        domains = scanner._generate_alternate_domains(
            "City of Test; DROP TABLE users",
            "",
        )
        # Should still produce valid-looking domains
        for d in domains:
            assert "/" not in d
            assert ";" not in d

    @patch.object(scanner, "fetch")
    def test_is_safe_url_called_before_fetch(self, mock_fetch):
        """Every URL must be validated by is_safe_url() before fetching."""
        calls = []
        original_is_safe = scanner.is_safe_url

        def tracking_is_safe(url):
            calls.append(url)
            return False  # Block all

        with patch.object(scanner, "is_safe_url", side_effect=tracking_is_safe):
            scanner._probe_alternate_domains("Test County", "")

        # fetch should never have been called (all blocked by is_safe_url)
        mock_fetch.assert_not_called()
        # But is_safe_url should have been called multiple times
        assert len(calls) > 0


# ---------------------------------------------------------------------------
# Existing function: _normalize_rest_directory
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# State extraction from jurisdiction name
# ---------------------------------------------------------------------------

class TestExtractStateFromName:
    """Tests for _extract_state_from_name()."""

    def test_comma_abbreviation(self):
        """'Lake County, CA' → 'ca'"""
        assert scanner._extract_state_from_name("Lake County, CA") == "ca"

    def test_comma_full_name(self):
        """'Franklin County, Ohio' → 'oh'"""
        assert scanner._extract_state_from_name("Franklin County, Ohio") == "oh"

    def test_space_abbreviation(self):
        """'Lake County OH' → 'oh'"""
        assert scanner._extract_state_from_name("Lake County OH") == "oh"

    def test_full_state_suffix(self):
        """'City of Austin, Texas' → 'tx'"""
        assert scanner._extract_state_from_name("City of Austin, Texas") == "tx"

    def test_florida(self):
        assert scanner._extract_state_from_name("Miami-Dade County, FL") == "fl"

    def test_no_state(self):
        assert scanner._extract_state_from_name("Lake County") == ""

    def test_empty(self):
        assert scanner._extract_state_from_name("") == ""


# ---------------------------------------------------------------------------
# State-specific domain generation (CA, OH, FL, TX)
# ---------------------------------------------------------------------------

class TestCaliforniaPatterns:
    """Tests for CA-specific alternate domain generation."""

    def test_ca_county_from_url(self):
        """CA counties should get CA-specific patterns via URL."""
        domains = scanner._generate_alternate_domains(
            "Lake County",
            "https://www.lakecountyca.gov",
        )
        # Should include CA-specific patterns
        assert "lake.ca.gov" in domains
        assert "lakecounty.org" in domains

    def test_ca_county_from_name(self):
        """CA counties should get CA-specific patterns via name suffix."""
        domains = scanner._generate_alternate_domains(
            "Lake County, CA", ""
        )
        assert "lake.ca.gov" in domains
        assert "lakecounty.org" in domains
        # Should also get general state-qualified patterns
        assert "lakeca.gov" in domains

    def test_ca_city_ci_pattern(self):
        """CA cities should get ci.{name}.ca.us pattern."""
        domains = scanner._generate_alternate_domains(
            "City of Milpitas, CA", ""
        )
        assert "ci.milpitas.ca.us" in domains
        assert "milpitas.ca.us" in domains

    def test_ca_county_initials_gov_org(self):
        """CA counties should get {initials}gov.org pattern (e.g. sjgov.org)."""
        domains = scanner._generate_alternate_domains(
            "San Joaquin County, CA", ""
        )
        assert "sjgov.org" in domains

    def test_ca_contra_costa(self):
        """Contra Costa County, CA should produce cccounty and CA patterns."""
        domains = scanner._generate_alternate_domains(
            "Contra Costa County",
            "https://www.contracosta.ca.gov",
        )
        assert any("cccounty" in d for d in domains)
        assert "contra.ca.gov" in domains
        assert "ccgov.org" in domains


class TestOhioPatterns:
    """Tests for OH-specific alternate domain generation."""

    def test_oh_county_from_name(self):
        """OH counties should get OH-specific patterns via name."""
        domains = scanner._generate_alternate_domains(
            "Franklin County, OH", ""
        )
        assert "franklincountyoh.org" in domains
        assert "franklinohio.gov" in domains
        assert "franklinoh.us" in domains
        assert "franklincountyohio.gov" in domains

    def test_oh_county_auditor_pattern(self):
        """OH counties should get auditor/engineer domain patterns."""
        domains = scanner._generate_alternate_domains(
            "Franklin County, Ohio", ""
        )
        assert "franklincountyauditor.org" in domains
        assert "franklincountyengineer.org" in domains

    def test_oh_county_legacy(self):
        """OH counties should get co.{name}.oh.us legacy pattern."""
        domains = scanner._generate_alternate_domains(
            "Franklin County",
            "https://franklincountyoh.gov",
        )
        # Should detect 'oh' from URL suffix
        assert "co.franklin.oh.us" in domains

    def test_oh_city(self):
        """OH cities should get OH-specific patterns."""
        domains = scanner._generate_alternate_domains(
            "City of Columbus, OH", ""
        )
        assert "columbusohio.gov" in domains
        assert "ci.columbus.oh.us" in domains
        assert "columbus.oh.us" in domains


class TestFloridaPatterns:
    """Tests for FL-specific alternate domain generation."""

    def test_fl_county_from_name(self):
        """FL counties should get FL-specific patterns via name."""
        domains = scanner._generate_alternate_domains(
            "Hillsborough County, FL", ""
        )
        assert "hillsboroughcountyfl.gov" in domains
        assert "hillsboroughfl.gov" in domains
        assert "hillsboroughcounty.org" in domains
        assert "hillsboroughfl.us" in domains

    def test_fl_county_appraiser(self):
        """FL counties should get property appraiser patterns."""
        domains = scanner._generate_alternate_domains(
            "Hillsborough County, Florida", ""
        )
        assert "hillsboroughpa.com" in domains
        assert "hillsboroughappraiser.com" in domains

    def test_fl_city(self):
        """FL cities should get FL-specific patterns."""
        domains = scanner._generate_alternate_domains(
            "City of Tampa, FL", ""
        )
        assert "tampafl.gov" in domains
        assert "tampafl.us" in domains
        assert "ci.tampa.fl.us" in domains


class TestTexasPatterns:
    """Tests for TX-specific alternate domain generation."""

    def test_tx_county_from_name(self):
        """TX counties should get TX-specific patterns via name."""
        domains = scanner._generate_alternate_domains(
            "Harris County, TX", ""
        )
        assert "harriscountytx.org" in domains
        assert "harriscounty.org" in domains
        assert "harristx.us" in domains
        assert "harriscountytx.gov" in domains

    def test_tx_county_cad_pattern(self):
        """TX counties should get appraisal district (CAD) patterns."""
        domains = scanner._generate_alternate_domains(
            "Harris County, Texas", ""
        )
        assert "harriscad.org" in domains
        assert "harrisad.org" in domains

    def test_tx_city(self):
        """TX cities should get TX-specific patterns."""
        domains = scanner._generate_alternate_domains(
            "City of Austin, TX", ""
        )
        assert "austintx.gov" in domains
        assert "austintexas.gov" in domains
        assert "austintx.us" in domains
        assert "ci.austin.tx.us" in domains


class TestStateExtractionFallback:
    """Tests that state abbreviation is extracted from name when URL lacks it."""

    def test_state_from_name_when_url_has_no_state(self):
        """State should be extracted from name when URL domain lacks state code."""
        domains = scanner._generate_alternate_domains(
            "Franklin County, OH",
            "https://www.franklincountyohio.gov",  # no 2-letter state in domain
        )
        # Should still get OH patterns because state is in the name
        assert "franklincountyoh.org" in domains

    def test_state_from_url_preferred_over_name(self):
        """URL-based state detection should take precedence."""
        domains = scanner._generate_alternate_domains(
            "Lake County",  # no state in name
            "https://www.lakecountyca.gov",  # 'ca' in domain
        )
        # Should detect CA from URL and generate CA patterns
        assert "lake.ca.gov" in domains


class TestDomainGenerationSecurity:
    """Security tests for the enhanced domain generation."""

    def test_no_special_chars_in_generated_domains(self):
        """All generated domains should be clean — no injection vectors."""
        for name, url in [
            ("Franklin County, OH", "https://example.oh.us"),
            ("City of Austin, TX", "https://austintx.gov"),
            ("Hillsborough County, FL", ""),
            ("San Joaquin County, CA", ""),
        ]:
            domains = scanner._generate_alternate_domains(name, url)
            for d in domains:
                assert " " not in d, f"Domain has space: {d}"
                assert "?" not in d, f"Domain has query: {d}"
                assert "#" not in d, f"Domain has fragment: {d}"
                assert "@" not in d, f"Domain has userinfo: {d}"
                # Domains may contain dots and hyphens but not other specials
                assert all(c.isalnum() or c in ".-" for c in d), \
                    f"Domain has invalid char: {d}"

    def test_domain_count_bounded(self):
        """Even with state-specific patterns, domain count stays reasonable.
        Too many domains = too many HTTP probes = DoS risk."""
        for name in [
            "Franklin County, OH",
            "Contra Costa County, CA",
            "Hillsborough County, FL",
            "Harris County, TX",
        ]:
            domains = scanner._generate_alternate_domains(name, "")
            # Should not exceed ~80 domains (16 prefixes × 5 TLDs = 80 combos
            # per domain + state-specific — but many are deduplicated)
            assert len(domains) <= 80, \
                f"Too many domains for {name}: {len(domains)}"

    def test_no_duplicates_with_state_patterns(self):
        """Deduplication should still work with state-specific patterns."""
        for name in [
            "Franklin County, OH",
            "Lake County, CA",
            "City of Tampa, FL",
            "City of Austin, TX",
        ]:
            domains = scanner._generate_alternate_domains(name, "")
            assert len(domains) == len(set(d.lower() for d in domains)), \
                f"Duplicate domains for {name}"


class TestNormalizeRestDirectory:
    """Regression tests for REST directory normalization."""

    def test_full_service_url(self):
        url = "https://gis.cccounty.us/arcgis/rest/services/CCMAP/CCMAP/MapServer/3"
        assert scanner._normalize_rest_directory(url) == \
            "https://gis.cccounty.us/arcgis/rest/services"

    def test_already_root(self):
        url = "https://gis.example.gov/arcgis/rest/services"
        assert scanner._normalize_rest_directory(url) == url

    def test_no_rest_services(self):
        url = "https://gis.example.gov/other/path"
        assert scanner._normalize_rest_directory(url) == url
