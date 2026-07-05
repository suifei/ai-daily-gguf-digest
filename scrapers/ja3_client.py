"""JA3-simulating HTTP client using curl_cffi.

Provides browser-like TLS fingerprints that evade anti-bot detection.
Supports Chrome/Edge/Firefox JA3 profiles.
"""
from curl_cffi import requests as cffi_requests
import logging

logger = logging.getLogger(__name__)

# JA3 fingerprint presets (TLS handshake level)
FINGERPRINTS = {
    "chrome": "chrome",
    "edge": "edge",
    "firefox": "firefox",
    "safari": "safari",
}


def ja3_session(profile="chrome", impersonate=None):
    """Create a curl_cffi session with browser JA3 fingerprint.
    
    Args:
        profile: JA3 fingerprint preset (chrome, edge, firefox, safari)
        impersonate: HTTP version to impersonate (auto, http1.1, http2, http3)
    
    Returns:
        curl_cffi requests.Session
    """
    if impersonate is None:
        impersonate = profile
    
    try:
        sess = cffi_requests.Session(impersonate=impersonate)
        logger.info(f"JA3 session created: profile={profile}, impersonate={impersonate}")
        return sess
    except Exception as e:
        logger.warning(f"JA3 session creation failed: {e}")
        return None


def ja3_get(url, params=None, headers=None, timeout=30, profile="chrome"):
    """Make a GET request with JA3 browser fingerprint."""
    sess = ja3_session(profile=profile)
    if sess is None:
        logger.warning(f"JA3 session unavailable for {url}, falling back to requests")
        return None
    
    try:
        resp = sess.get(url, params=params, headers=headers, timeout=timeout)
        return resp
    except Exception as e:
        logger.warning(f"JA3 GET failed for {url}: {e}")
        return None
    finally:
        sess.close()


def ja3_post(url, data=None, json=None, headers=None, timeout=30, profile="chrome"):
    """Make a POST request with JA3 browser fingerprint."""
    sess = ja3_session(profile=profile)
    if sess is None:
        return None
    
    try:
        resp = sess.post(url, data=data, json=json, headers=headers, timeout=timeout)
        return resp
    except Exception as e:
        logger.warning(f"JA3 POST failed for {url}: {e}")
        return None
    finally:
        sess.close()
