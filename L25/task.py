#!/usr/bin/env python3
"""L25 - timetravel: CLI assistant for operating CHRONOS-P1 time machine.

The assistant guides a human operator through 3 jumps:
  Phase 1: current -> 5 Nov 2238  (pick up batteries)
  Phase 2: 2238    -> 10 Apr 2026 (return to today)
  Phase 3: 2026    -> 12 Nov 2024 (open time tunnel to meet Rafal)

Usage:
    python L25/task.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "timetravel"
L25_DIR = Path(__file__).parent
VERIFICATION_FILE = L25_DIR / "verification_result.json"

# ---------------------------------------------------------------------------
# internalMode ranges (automatic, cannot be set manually)
#   1 -> year < 2000
#   2 -> 2000 <= year <= 2150
#   3 -> 2151 <= year <= 2300
#   4 -> year > 2300
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PWR protection table (from device documentation)
# ---------------------------------------------------------------------------

PWR_TABLE: dict[int, int] = {
    # 1500-1599
    1500: 3, 1501: 3, 1502: 1, 1503: 3, 1504: 1, 1505: 3, 1506: 1, 1507: 2, 1508: 3, 1509: 2,
    1510: 2, 1511: 3, 1512: 3, 1513: 3, 1514: 1, 1515: 2, 1516: 3, 1517: 2, 1518: 3, 1519: 2,
    1520: 3, 1521: 3, 1522: 2, 1523: 1, 1524: 2, 1525: 3, 1526: 2, 1527: 3, 1528: 2, 1529: 1,
    1530: 3, 1531: 1, 1532: 2, 1533: 3, 1534: 3, 1535: 2, 1536: 3, 1537: 3, 1538: 3, 1539: 3,
    1540: 1, 1541: 3, 1542: 3, 1543: 2, 1544: 1, 1545: 3, 1546: 1, 1547: 3, 1548: 3, 1549: 3,
    1550: 1, 1551: 1, 1552: 3, 1553: 1, 1554: 1, 1555: 2, 1556: 2, 1557: 3, 1558: 1, 1559: 2,
    1560: 1, 1561: 1, 1562: 1, 1563: 2, 1564: 3, 1565: 3, 1566: 1, 1567: 2, 1568: 1, 1569: 3,
    1570: 2, 1571: 3, 1572: 2, 1573: 3, 1574: 3, 1575: 2, 1576: 3, 1577: 3, 1578: 1, 1579: 2,
    1580: 1, 1581: 2, 1582: 2, 1583: 1, 1584: 1, 1585: 3, 1586: 1, 1587: 3, 1588: 1, 1589: 3,
    1590: 3, 1591: 1, 1592: 2, 1593: 1, 1594: 2, 1595: 3, 1596: 1, 1597: 1, 1598: 1, 1599: 3,
    # 1600-1699
    1600: 2, 1601: 4, 1602: 2, 1603: 4, 1604: 4, 1605: 3, 1606: 2, 1607: 2, 1608: 2, 1609: 4,
    1610: 4, 1611: 2, 1612: 2, 1613: 2, 1614: 4, 1615: 3, 1616: 3, 1617: 4, 1618: 2, 1619: 2,
    1620: 4, 1621: 2, 1622: 4, 1623: 2, 1624: 4, 1625: 3, 1626: 2, 1627: 2, 1628: 3, 1629: 2,
    1630: 2, 1631: 3, 1632: 2, 1633: 2, 1634: 3, 1635: 4, 1636: 3, 1637: 4, 1638: 4, 1639: 2,
    1640: 4, 1641: 3, 1642: 2, 1643: 2, 1644: 3, 1645: 3, 1646: 4, 1647: 4, 1648: 4, 1649: 2,
    1650: 3, 1651: 4, 1652: 3, 1653: 4, 1654: 3, 1655: 2, 1656: 4, 1657: 3, 1658: 4, 1659: 4,
    1660: 3, 1661: 4, 1662: 2, 1663: 2, 1664: 2, 1665: 4, 1666: 4, 1667: 3, 1668: 4, 1669: 4,
    1670: 2, 1671: 4, 1672: 4, 1673: 4, 1674: 3, 1675: 2, 1676: 2, 1677: 3, 1678: 3, 1679: 3,
    1680: 4, 1681: 2, 1682: 2, 1683: 3, 1684: 3, 1685: 4, 1686: 3, 1687: 3, 1688: 4, 1689: 3,
    1690: 2, 1691: 2, 1692: 3, 1693: 3, 1694: 2, 1695: 4, 1696: 4, 1697: 4, 1698: 3, 1699: 3,
    # 1700-1799
    1700: 3, 1701: 3, 1702: 3, 1703: 3, 1704: 4, 1705: 4, 1706: 5, 1707: 4, 1708: 4, 1709: 4,
    1710: 3, 1711: 4, 1712: 3, 1713: 3, 1714: 3, 1715: 3, 1716: 3, 1717: 4, 1718: 4, 1719: 4,
    1720: 5, 1721: 4, 1722: 4, 1723: 5, 1724: 3, 1725: 3, 1726: 3, 1727: 4, 1728: 5, 1729: 4,
    1730: 4, 1731: 5, 1732: 5, 1733: 4, 1734: 3, 1735: 4, 1736: 3, 1737: 4, 1738: 3, 1739: 3,
    1740: 3, 1741: 4, 1742: 4, 1743: 5, 1744: 5, 1745: 3, 1746: 4, 1747: 4, 1748: 4, 1749: 5,
    1750: 5, 1751: 5, 1752: 3, 1753: 5, 1754: 4, 1755: 4, 1756: 5, 1757: 4, 1758: 3, 1759: 5,
    1760: 3, 1761: 4, 1762: 3, 1763: 5, 1764: 5, 1765: 4, 1766: 3, 1767: 5, 1768: 3, 1769: 3,
    1770: 5, 1771: 3, 1772: 4, 1773: 4, 1774: 4, 1775: 4, 1776: 5, 1777: 5, 1778: 4, 1779: 3,
    1780: 4, 1781: 3, 1782: 4, 1783: 3, 1784: 3, 1785: 4, 1786: 5, 1787: 5, 1788: 3, 1789: 5,
    1790: 4, 1791: 5, 1792: 3, 1793: 4, 1794: 5, 1795: 5, 1796: 4, 1797: 3, 1798: 5, 1799: 4,
    # 1800-1899
    1800: 4, 1801: 6, 1802: 4, 1803: 6, 1804: 6, 1805: 5, 1806: 7, 1807: 4, 1808: 4, 1809: 4,
    1810: 8, 1811: 5, 1812: 7, 1813: 4, 1814: 6, 1815: 5, 1816: 4, 1817: 4, 1818: 8, 1819: 5,
    1820: 7, 1821: 5, 1822: 8, 1823: 6, 1824: 8, 1825: 5, 1826: 4, 1827: 8, 1828: 7, 1829: 8,
    1830: 4, 1831: 6, 1832: 5, 1833: 6, 1834: 5, 1835: 8, 1836: 8, 1837: 5, 1838: 4, 1839: 7,
    1840: 5, 1841: 7, 1842: 4, 1843: 8, 1844: 7, 1845: 6, 1846: 4, 1847: 6, 1848: 7, 1849: 6,
    1850: 6, 1851: 7, 1852: 4, 1853: 6, 1854: 4, 1855: 4, 1856: 5, 1857: 6, 1858: 8, 1859: 8,
    1860: 4, 1861: 4, 1862: 5, 1863: 7, 1864: 7, 1865: 4, 1866: 4, 1867: 6, 1868: 7, 1869: 5,
    1870: 7, 1871: 7, 1872: 8, 1873: 8, 1874: 5, 1875: 7, 1876: 7, 1877: 6, 1878: 7, 1879: 7,
    1880: 4, 1881: 4, 1882: 5, 1883: 4, 1884: 5, 1885: 7, 1886: 4, 1887: 7, 1888: 5, 1889: 8,
    1890: 8, 1891: 7, 1892: 6, 1893: 6, 1894: 4, 1895: 4, 1896: 4, 1897: 8, 1898: 7, 1899: 8,
    # 1900-1999
    1900: 10, 1901: 8,  1902: 7,  1903: 8,  1904: 9,  1905: 9,  1906: 10, 1907: 8,  1908: 11, 1909: 10,
    1910: 8,  1911: 8,  1912: 8,  1913: 8,  1914: 14, 1915: 12, 1916: 14, 1917: 13, 1918: 13, 1919: 10,
    1920: 10, 1921: 11, 1922: 11, 1923: 8,  1924: 10, 1925: 8,  1926: 9,  1927: 10, 1928: 12, 1929: 9,
    1930: 8,  1931: 11, 1932: 8,  1933: 12, 1934: 10, 1935: 9,  1936: 9,  1937: 12, 1938: 10, 1939: 16,
    1940: 16, 1941: 16, 1942: 15, 1943: 16, 1944: 17, 1945: 17, 1946: 14, 1947: 16, 1948: 15, 1949: 14,
    1950: 11, 1951: 15, 1952: 12, 1953: 16, 1954: 15, 1955: 12, 1956: 11, 1957: 14, 1958: 14, 1959: 14,
    1960: 10, 1961: 11, 1962: 12, 1963: 9,  1964: 13, 1965: 14, 1966: 10, 1967: 12, 1968: 14, 1969: 10,
    1970: 9,  1971: 13, 1972: 12, 1973: 9,  1974: 10, 1975: 13, 1976: 14, 1977: 14, 1978: 9,  1979: 10,
    1980: 12, 1981: 12, 1982: 13, 1983: 11, 1984: 13, 1985: 10, 1986: 16, 1987: 13, 1988: 10, 1989: 14,
    1990: 11, 1991: 13, 1992: 10, 1993: 10, 1994: 14, 1995: 13, 1996: 10, 1997: 12, 1998: 13, 1999: 14,
    # 2000-2099
    2000: 13, 2001: 12, 2002: 17, 2003: 13, 2004: 15, 2005: 14, 2006: 17, 2007: 12, 2008: 12, 2009: 13,
    2010: 12, 2011: 17, 2012: 15, 2013: 14, 2014: 13, 2015: 16, 2016: 15, 2017: 14, 2018: 17, 2019: 14,
    2020: 19, 2021: 18, 2022: 18, 2023: 18, 2024: 19, 2025: 18, 2026: 28, 2027: 31, 2028: 35, 2029: 28,
    2030: 32, 2031: 30, 2032: 36, 2033: 28, 2034: 28, 2035: 33, 2036: 39, 2037: 41, 2038: 48, 2039: 50,
    2040: 47, 2041: 50, 2042: 42, 2043: 49, 2044: 48, 2045: 42, 2046: 45, 2047: 43, 2048: 44, 2049: 47,
    2050: 41, 2051: 48, 2052: 50, 2053: 61, 2054: 48, 2055: 59, 2056: 64, 2057: 53, 2058: 48, 2059: 57,
    2060: 49, 2061: 52, 2062: 59, 2063: 56, 2064: 53, 2065: 61, 2066: 50, 2067: 59, 2068: 53, 2069: 54,
    2070: 61, 2071: 53, 2072: 51, 2073: 64, 2074: 60, 2075: 51, 2076: 59, 2077: 63, 2078: 63, 2079: 59,
    2080: 58, 2081: 72, 2082: 63, 2083: 68, 2084: 67, 2085: 58, 2086: 66, 2087: 72, 2088: 70, 2089: 60,
    2090: 58, 2091: 69, 2092: 66, 2093: 61, 2094: 58, 2095: 61, 2096: 69, 2097: 69, 2098: 63, 2099: 63,
    # 2100-2199
    2100: 67, 2101: 80, 2102: 82, 2103: 72, 2104: 73, 2105: 75, 2106: 78, 2107: 75, 2108: 73, 2109: 69,
    2110: 80, 2111: 68, 2112: 72, 2113: 76, 2114: 82, 2115: 79, 2116: 77, 2117: 82, 2118: 79, 2119: 80,
    2120: 74, 2121: 73, 2122: 79, 2123: 80, 2124: 71, 2125: 68, 2126: 79, 2127: 78, 2128: 68, 2129: 73,
    2130: 81, 2131: 68, 2132: 70, 2133: 76, 2134: 78, 2135: 70, 2136: 68, 2137: 76, 2138: 79, 2139: 79,
    2140: 77, 2141: 71, 2142: 70, 2143: 71, 2144: 68, 2145: 72, 2146: 78, 2147: 81, 2148: 75, 2149: 72,
    2150: 82, 2151: 86, 2152: 83, 2153: 81, 2154: 76, 2155: 75, 2156: 77, 2157: 79, 2158: 84, 2159: 83,
    2160: 80, 2161: 88, 2162: 84, 2163: 88, 2164: 75, 2165: 88, 2166: 87, 2167: 82, 2168: 83, 2169: 81,
    2170: 88, 2171: 82, 2172: 83, 2173: 78, 2174: 78, 2175: 79, 2176: 78, 2177: 85, 2178: 74, 2179: 85,
    2180: 85, 2181: 84, 2182: 88, 2183: 80, 2184: 81, 2185: 84, 2186: 77, 2187: 85, 2188: 80, 2189: 78,
    2190: 82, 2191: 76, 2192: 80, 2193: 88, 2194: 84, 2195: 78, 2196: 86, 2197: 86, 2198: 85, 2199: 79,
    # 2200-2299
    2200: 82, 2201: 88, 2202: 87, 2203: 89, 2204: 86, 2205: 89, 2206: 92, 2207: 85, 2208: 91, 2209: 93,
    2210: 91, 2211: 85, 2212: 82, 2213: 91, 2214: 86, 2215: 86, 2216: 83, 2217: 89, 2218: 94, 2219: 86,
    2220: 84, 2221: 89, 2222: 83, 2223: 91, 2224: 83, 2225: 91, 2226: 82, 2227: 82, 2228: 92, 2229: 88,
    2230: 86, 2231: 92, 2232: 93, 2233: 88, 2234: 86, 2235: 84, 2236: 89, 2237: 91, 2238: 91, 2239: 88,
    2240: 87, 2241: 83, 2242: 83, 2243: 88, 2244: 94, 2245: 84, 2246: 91, 2247: 92, 2248: 91, 2249: 82,
    2250: 88, 2251: 82, 2252: 85, 2253: 93, 2254: 85, 2255: 85, 2256: 87, 2257: 94, 2258: 89, 2259: 82,
    2260: 82, 2261: 85, 2262: 91, 2263: 90, 2264: 82, 2265: 84, 2266: 85, 2267: 90, 2268: 84, 2269: 94,
    2270: 94, 2271: 85, 2272: 94, 2273: 87, 2274: 88, 2275: 85, 2276: 83, 2277: 94, 2278: 94, 2279: 87,
    2280: 91, 2281: 90, 2282: 85, 2283: 82, 2284: 85, 2285: 87, 2286: 93, 2287: 87, 2288: 87, 2289: 93,
    2290: 88, 2291: 82, 2292: 84, 2293: 83, 2294: 88, 2295: 85, 2296: 91, 2297: 83, 2298: 93, 2299: 92,
    # 2300-2399
    2300: 92, 2301: 93, 2302: 92, 2303: 89, 2304: 91, 2305: 90, 2306: 90, 2307: 93, 2308: 94, 2309: 90,
    2310: 93, 2311: 88, 2312: 92, 2313: 94, 2314: 97, 2315: 96, 2316: 88, 2317: 89, 2318: 97, 2319: 95,
    2320: 91, 2321: 94, 2322: 94, 2323: 93, 2324: 94, 2325: 91, 2326: 92, 2327: 92, 2328: 88, 2329: 90,
    2330: 92, 2331: 92, 2332: 88, 2333: 97, 2334: 93, 2335: 94, 2336: 88, 2337: 97, 2338: 88, 2339: 96,
    2340: 97, 2341: 90, 2342: 89, 2343: 88, 2344: 91, 2345: 90, 2346: 95, 2347: 96, 2348: 95, 2349: 93,
    2350: 92, 2351: 97, 2352: 95, 2353: 91, 2354: 95, 2355: 90, 2356: 92, 2357: 93, 2358: 93, 2359: 90,
    2360: 91, 2361: 89, 2362: 93, 2363: 93, 2364: 90, 2365: 95, 2366: 92, 2367: 89, 2368: 94, 2369: 90,
    2370: 88, 2371: 90, 2372: 90, 2373: 92, 2374: 89, 2375: 96, 2376: 95, 2377: 95, 2378: 96, 2379: 93,
    2380: 92, 2381: 93, 2382: 89, 2383: 92, 2384: 91, 2385: 94, 2386: 96, 2387: 95, 2388: 93, 2389: 95,
    2390: 91, 2391: 91, 2392: 96, 2393: 96, 2394: 94, 2395: 89, 2396: 88, 2397: 93, 2398: 88, 2399: 88,
    # 2400-2499
    2400: 92, 2401: 95, 2402: 99, 2403: 99, 2404: 99, 2405: 99, 2406: 95, 2407: 95, 2408: 94, 2409: 95,
    2410: 94, 2411: 94, 2412: 99, 2413: 94, 2414: 97, 2415: 99, 2416: 96, 2417: 99, 2418: 99, 2419: 96,
    2420: 99, 2421: 98, 2422: 99, 2423: 99, 2424: 95, 2425: 99, 2426: 98, 2427: 96, 2428: 94, 2429: 94,
    2430: 95, 2431: 99, 2432: 98, 2433: 96, 2434: 94, 2435: 99, 2436: 97, 2437: 95, 2438: 94, 2439: 99,
    2440: 97, 2441: 99, 2442: 97, 2443: 95, 2444: 97, 2445: 95, 2446: 99, 2447: 99, 2448: 95, 2449: 97,
    2450: 98, 2451: 94, 2452: 98, 2453: 95, 2454: 97, 2455: 95, 2456: 97, 2457: 99, 2458: 98, 2459: 99,
    2460: 96, 2461: 99, 2462: 94, 2463: 96, 2464: 98, 2465: 96, 2466: 99, 2467: 96, 2468: 95, 2469: 96,
    2470: 95, 2471: 99, 2472: 96, 2473: 96, 2474: 97, 2475: 95, 2476: 95, 2477: 97, 2478: 95, 2479: 95,
    2480: 97, 2481: 95, 2482: 99, 2483: 94, 2484: 95, 2485: 99, 2486: 96, 2487: 95, 2488: 97, 2489: 94,
    2490: 99, 2491: 95, 2492: 94, 2493: 99, 2494: 94, 2495: 99, 2496: 96, 2497: 97, 2498: 95, 2499: 97,
}

# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------


def calc_sync_ratio(day: int, month: int, year: int) -> float:
    """Calculate syncRatio for a target date.

    Formula: (day*8 + month*12 + year*7) % 101
    Result 0-100 mapped to 0.00-1.00 (two decimal places).
    100 -> 1.00, 0 -> 0.00
    """
    raw = (day * 8 + month * 12 + year * 7) % 101
    if raw == 100:
        return 1.00
    return round(raw / 100.0, 2)


def required_internal_mode(year: int) -> int:
    """Return the internalMode required for a target year."""
    if year < 2000:
        return 1
    elif year <= 2150:
        return 2
    elif year <= 2300:
        return 3
    return 4


def pwr_for_year(year: int) -> int:
    """Look up recommended PWR protection level for target year."""
    return PWR_TABLE.get(year, -1)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def api_call(action: str, **kwargs) -> dict:
    """POST to /verify with the given action and optional parameters."""
    answer: dict = {"action": action}
    answer.update(kwargs)
    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": answer,
    }
    try:
        resp = requests.post(VERIFY_URL, json=payload, timeout=30)
        data = resp.json()
    except Exception as exc:
        print(f"  [BLAD API] {exc}")
        return {}
    print(f"  [API /{action}] -> {json.dumps(data, ensure_ascii=False)}")
    return data


def configure_param(param: str, value: object) -> dict:
    """Configure a single device parameter via API."""
    return api_call("configure", param=param, value=value)


def get_config() -> dict:
    """Fetch current device configuration."""
    return api_call("getConfig")


def get_api_help() -> dict:
    """Fetch API help."""
    return api_call("help")


def reset_device() -> dict:
    """Reset the device."""
    return api_call("reset")


# ---------------------------------------------------------------------------
# Stabilization hint extraction
# ---------------------------------------------------------------------------


def extract_stabilization_hint(response: dict) -> str | None:
    """Try to extract a stabilization value/hint from an API response dict."""
    if not response:
        return None

    # Direct key matches
    for key in ("stabilization", "hint", "tip", "info", "message", "msg", "note"):
        val = response.get(key)
        if val is not None:
            s = str(val).strip()
            if s:
                return s

    # Scan nested dicts one level deep
    for val in response.values():
        if isinstance(val, dict):
            for k2, v2 in val.items():
                if "stab" in k2.lower() and v2 is not None:
                    return str(v2)

    # Last resort: find first numeric-looking value
    flat = json.dumps(response, ensure_ascii=False)
    m = re.search(r'"(?:stabilization|stabil)[^"]*"\s*:\s*([0-9.]+)', flat, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def configure_date_and_sync(day: int, month: int, year: int) -> None:
    """Set day, month, year and syncRatio via API."""
    sync = calc_sync_ratio(day, month, year)
    raw = (day * 8 + month * 12 + year * 7) % 101
    print(f"\n  syncRatio dla {day}/{month}/{year}:")
    print(f"    ({day}*8 + {month}*12 + {year}*7) % 101 = {raw} -> {sync}")

    for param, value in [("day", day), ("month", month), ("year", year), ("syncRatio", sync)]:
        print(f"\n  [API] Ustawiam {param}={value}")
        configure_param(param, value)
        time.sleep(0.5)


def fetch_and_set_stabilization() -> None:
    """Read stabilization hint from API and configure it."""
    print("\n  [API] Pobieranie wskazowki stabilization (getConfig po ustawieniu daty)...")
    data = get_config()
    hint = extract_stabilization_hint(data)

    if hint:
        print(f"\n  [HINT] Wskazowka stabilization: {hint}")
        # Try to parse as number
        try:
            num_val: object
            if "." in hint:
                num_val = float(hint)
            else:
                num_val = int(hint)
            print(f"\n  [API] Ustawiam stabilization={num_val}")
            configure_param("stabilization", num_val)
            return
        except ValueError:
            print(f"  [INFO] Nie mozna sparsowac '{hint}' jako liczby.")

    # Manual fallback
    print("  [INFO] Nie wykryto wartosci numerycznej. Sprawdz powyzszy wynik getConfig.")
    print("         Szukaj klucza 'stabilization' lub podobnego.")
    raw_val = input("  Podaj wartosc stabilization (lub Enter aby pominac): ").strip()
    if raw_val:
        try:
            configure_param("stabilization", float(raw_val) if "." in raw_val else int(raw_val))
        except ValueError:
            configure_param("stabilization", raw_val)


def poll_internal_mode(expected_mode: int, interval: int = 4) -> None:
    """Poll getConfig until internalMode matches expected_mode."""
    print(f"\n  [CZEKAM] az internalMode = {expected_mode}  (Ctrl+C aby przerwac)\n")
    while True:
        try:
            data = get_config()
            current = None

            # Try direct key
            if "internalMode" in data:
                current = data["internalMode"]
            # Try nested config object
            elif isinstance(data.get("config"), dict):
                current = data["config"].get("internalMode")
            # Fallback: grep serialized JSON
            else:
                m = re.search(r'"internalMode"\s*:\s*(\d+)', json.dumps(data))
                if m:
                    current = int(m.group(1))

            if current is not None:
                print(f"  [MODE] internalMode = {current}  (szukamy: {expected_mode})")
                if int(current) == expected_mode:
                    print(f"\n  [OK] internalMode = {expected_mode} — GOTOWE DO SKOKU!\n")
                    return
            else:
                print(f"  [MODE] Nie mozna odczytac internalMode. Pelna odpowiedz powyzej.")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  [STOP] Polling przerwany przez uzytkownika.")
            return


def print_ui_instructions(pwr: int, pt_a: bool, pt_b: bool, mode: int) -> None:
    """Print manual UI instructions for the operator."""
    print()
    print("=" * 62)
    print("  INSTRUKCJE DLA OPERATORA — interfejs webowy:")
    print("  https://hub.ag3nts.org/timetravel_preview")
    print("=" * 62)
    print(f"  1. Upewnij sie, ze urzadzenie jest w trybie STANDBY")
    print(f"  2. Ustaw suwak  PWR = {pwr}")
    pt_a_txt = "WLACZ  [ON]" if pt_a else "WYLACZ [OFF]"
    pt_b_txt = "WLACZ  [ON]" if pt_b else "WYLACZ [OFF]"
    print(f"  3. PT-A: {pt_a_txt}")
    print(f"     PT-B: {pt_b_txt}")
    if pt_a and pt_b:
        print("     -> Tryb TUNELU CZASOWEGO (PT-A + PT-B jednoczesnie)")
    elif pt_a:
        print("     -> Skok w PRZESZLOSC (tylko PT-A)")
    elif pt_b:
        print("     -> Skok w PRZYSZLOSC (tylko PT-B)")
    print(f"  4. Poczekaj az internalMode = {mode}")
    print("  5. Przelacz urzadzenie na tryb ACTIVE")
    print("  6. Kliknij pulsujaca SFERE AKTYWACJI (musi byc zielona)")
    print("     (flux density musi pokazywac 100%)")
    print("=" * 62)


def check_for_flag(data: dict) -> str | None:
    """Search for {FLG:...} pattern anywhere in API response."""
    flat = json.dumps(data, ensure_ascii=False)
    m = re.search(r"\{FLG:[^}]+\}", flat)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------


def run_phase1() -> None:
    """Phase 1: Jump to 5 November 2238 to pick up batteries."""
    day, month, year = 5, 11, 2238
    pwr = pwr_for_year(year)
    mode = required_internal_mode(year)

    print()
    print("#" * 62)
    print("  FAZA 1 — skok do 5 listopada 2238 (odbiór baterii)")
    print("#" * 62)
    print(f"  Data docelowa : {day}/{month}/{year}")
    print(f"  PWR           : {pwr}")
    print(f"  PT            : PT-B (skok w przyszlosc)")
    print(f"  internalMode  : {mode} (zakres 2151-2300)")

    input("\n  [ENTER] aby rozpoczac konfiguracje API (urzadzenie musi byc w STANDBY)...")

    configure_date_and_sync(day, month, year)
    fetch_and_set_stabilization()

    print_ui_instructions(pwr, pt_a=False, pt_b=True, mode=mode)
    input("\n  [ENTER] kiedy ustawisz PWR i PT-B w interfejsie...")

    poll_internal_mode(mode)

    print("\n  TERAZ:")
    print("    1. Przelacz urzadzenie na ACTIVE w interfejsie")
    print("    2. Kliknij zielona sfere aktywacji")
    print("    3. W roku 2238 odbierz nowe baterie i wloz je do urzadzenia")
    input("\n  [ENTER] po wykonaniu skoku i odebraniu baterii...")
    print("\n  [OK] Faza 1 zakonczona.")


def run_phase2() -> None:
    """Phase 2: Return to 10 April 2026 (today)."""
    day, month, year = 10, 4, 2026
    pwr = pwr_for_year(year)
    mode = required_internal_mode(year)

    print()
    print("#" * 62)
    print("  FAZA 2 — powrot do 10 kwietnia 2026 (dzis)")
    print("#" * 62)
    print(f"  Data docelowa : {day}/{month}/{year}")
    print(f"  PWR           : {pwr}")
    print(f"  PT            : PT-A (skok w przeszlosc)")
    print(f"  internalMode  : {mode} (zakres 2000-2150)")

    input("\n  [ENTER] aby rozpoczac konfiguracje API (urzadzenie musi byc w STANDBY)...")

    configure_date_and_sync(day, month, year)
    fetch_and_set_stabilization()

    print_ui_instructions(pwr, pt_a=True, pt_b=False, mode=mode)
    input("\n  [ENTER] kiedy ustawisz PWR i PT-A w interfejsie...")

    poll_internal_mode(mode)

    print("\n  TERAZ:")
    print("    1. Przelacz urzadzenie na ACTIVE w interfejsie")
    print("    2. Kliknij zielona sfere aktywacji")
    input("\n  [ENTER] po powrocie do roku 2026...")
    print("\n  [OK] Faza 2 zakonczona.")


def run_phase3() -> None:
    """Phase 3: Open time tunnel to 12 November 2024."""
    day, month, year = 12, 11, 2024
    pwr = pwr_for_year(year)
    mode = required_internal_mode(year)

    print()
    print("#" * 62)
    print("  FAZA 3 — otwarcie tunelu do 12 listopada 2024")
    print("#" * 62)
    print(f"  Data docelowa : {day}/{month}/{year}")
    print(f"  PWR           : {pwr}")
    print(f"  PT            : PT-A + PT-B (tryb tunelu czasowego)")
    print(f"  internalMode  : {mode} (zakres 2000-2150)")
    print(f"  UWAGA         : bateria musi byc >= 60% przed otwarciem tunelu!")

    input("\n  [ENTER] aby sprawdzic stan baterii i rozpoczac konfiguracje...")

    print("\n  [API] Sprawdzam stan baterii...")
    cfg = get_config()
    cfg_str = json.dumps(cfg, ensure_ascii=False)
    m = re.search(r'"(?:battery|batter[a-z]*)"[^:]*:\s*"?(\d+)', cfg_str, re.IGNORECASE)
    if m:
        battery = int(m.group(1))
        print(f"  [INFO] Poziom baterii: {battery}%")
        if battery < 60:
            print(f"\n  [OSTRZEZENIE] Bateria = {battery}% — ponizej wymaganego 60%!")
            print("                Tunel moze nie zostac otwarty.")
            if input("  Kontynuowac mimo to? (t/n): ").strip().lower() != "t":
                return
    else:
        print("  [INFO] Nie mozna automatycznie odczytac poziomu baterii.")
        print("         Sprawdz interfejs webowy.")

    configure_date_and_sync(day, month, year)
    fetch_and_set_stabilization()

    print_ui_instructions(pwr, pt_a=True, pt_b=True, mode=mode)
    input("\n  [ENTER] kiedy ustawisz PWR, PT-A i PT-B w interfejsie...")

    poll_internal_mode(mode)

    print("\n  TERAZ:")
    print("    1. Przelacz urzadzenie na ACTIVE w interfejsie")
    print("    2. Kliknij zielona sfere aktywacji (otwiera tunel do 2024)")
    input("\n  [ENTER] po kliknieciu sfery...")

    print("\n  [API] Sprawdzam odpowiedz po otwarciu tunelu...")
    final = get_config()
    flag = check_for_flag(final)
    if flag:
        print(f"\n  *** FLAGA: {flag} ***\n")
        VERIFICATION_FILE.write_text(json.dumps(final, ensure_ascii=False, indent=2))
        print(f"  [ZAPISANO] {VERIFICATION_FILE}")
    else:
        print("  [INFO] Flaga nie pojawila sie w getConfig.")
        print("         Sprawdz odpowiedz ponizej lub interfejs webowy:")
        print(json.dumps(final, ensure_ascii=False, indent=2))

    print("\n  [OK] Faza 3 zakonczona.")


# ---------------------------------------------------------------------------
# Show helpers
# ---------------------------------------------------------------------------


def show_mission_overview() -> None:
    """Print mission overview with pre-computed parameters for all 3 phases."""
    phases = [
        (1, 5,  11, 2238, False, True,  "skok w przyszlosc — odbior baterii"),
        (2, 10,  4, 2026, True,  False, "skok w przeszlosc — powrot do dzis"),
        (3, 12, 11, 2024, True,  True,  "tunel czasu — spotkanie z Rafaem"),
    ]
    print()
    print("=" * 70)
    print("  PRZEGLAD MISJI — CHRONOS-P1  (3 skoki)")
    print("=" * 70)
    for phase, day, month, year, pt_a, pt_b, desc in phases:
        sync = calc_sync_ratio(day, month, year)
        raw = (day * 8 + month * 12 + year * 7) % 101
        mode = required_internal_mode(year)
        pwr = pwr_for_year(year)
        pt_parts = []
        if pt_a:
            pt_parts.append("PT-A")
        if pt_b:
            pt_parts.append("PT-B")
        print(f"\n  Faza {phase}: {day}/{month}/{year}  —  {desc}")
        print(f"    syncRatio    : ({day}*8 + {month}*12 + {year}*7) % 101 = {raw} -> {sync}")
        print(f"    internalMode : {mode}")
        print(f"    PWR          : {pwr}")
        print(f"    PT           : {' + '.join(pt_parts)}")
    print()
    print("  Uwaga: stabilization musi byc odczytana z API po ustawieniu daty.")
    print("=" * 70)


def show_current_config() -> None:
    """Show current device config."""
    print("\n  [API] Pobieranie aktualnej konfiguracji...")
    data = get_config()
    print("\n  Aktualna konfiguracja:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    flag = check_for_flag(data)
    if flag:
        print(f"\n  *** FLAGA ZNALEZIONA: {flag} ***")
        VERIFICATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main() -> None:
    print()
    print("=" * 62)
    print("  CHRONOS-P1 — Asystent CLI")
    print("  Zadanie: timetravel | endpoint: hub.ag3nts.org/verify")
    print("  UI: https://hub.ag3nts.org/timetravel_preview")
    print("=" * 62)

    while True:
        print()
        print("  MENU:")
        print("  1. Pokaz aktualna konfiguracje (getConfig)")
        print("  2. Przeglad misji — parametry wszystkich 3 skokow")
        print("  3. Faza 1 — skok do 5 listopada 2238  (odbior baterii)")
        print("  4. Faza 2 — powrot do 10 kwietnia 2026  (dzis)")
        print("  5. Faza 3 — otworz tunel do 12 listopada 2024")
        print("  6. Wywolaj help")
        print("  7. Reset urzadzenia")
        print("  0. Wyjdz")

        choice = input("\n  Wybierz opcje: ").strip()

        if choice == "0":
            print("  Do widzenia!")
            break
        elif choice == "1":
            show_current_config()
        elif choice == "2":
            show_mission_overview()
        elif choice == "3":
            run_phase1()
        elif choice == "4":
            run_phase2()
        elif choice == "5":
            run_phase3()
        elif choice == "6":
            get_api_help()
        elif choice == "7":
            if input("  Na pewno zresetowac urzadzenie? (t/n): ").strip().lower() == "t":
                reset_device()
        else:
            print("  Nieznana opcja, sprobuj ponownie.")


if __name__ == "__main__":
    main()
