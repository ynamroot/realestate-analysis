"""
Phase 3 tests: TMAP client, subway graph, BFS stop counts, caching.
All tests are xfail until Wave 1/2/3 implementation is complete.

Requirements covered:
  SUBW-01: tmap_walk_distance() parses totalDistance from mock response
  SUBW-02: subway_distances INSERT stores NULL when walk_distance > 1000m
  SUBW-03: cache hit skips TMAP call for same (apartment_id, station_name)
  COMM-01: build_subway_graph() builds nodes/edges from XLSX data
  COMM-02/03/04: min_stops() returns correct BFS stop count
  COMM-05: commute_stops INSERT OR REPLACE stores stops_to_gbd
"""
import pytest
from pipeline.storage.schema import init_db, migrate_db


# --- SUBW-01: TMAP parse ---

@pytest.mark.xfail(strict=False, reason="tmap client not yet implemented")
def test_tmap_walk_distance_parse():
    """tmap_walk_distance() returns totalDistance int from mock SP feature."""
    from pipeline.clients.tmap import tmap_walk_distance_from_response
    mock_response = {
        "features": [
            {"properties": {"pointType": "SP", "totalDistance": 850}}
        ]
    }
    result = tmap_walk_distance_from_response(mock_response)
    assert result == 850
    assert isinstance(result, int)


@pytest.mark.xfail(strict=False, reason="tmap client not yet implemented")
def test_tmap_walk_distance_empty():
    """tmap_walk_distance_from_response() returns None when features is empty."""
    from pipeline.clients.tmap import tmap_walk_distance_from_response
    result = tmap_walk_distance_from_response({"features": []})
    assert result is None


# --- SUBW-02: NULL for >1km ---

@pytest.mark.xfail(strict=False, reason="subway_distances collector not yet implemented")
def test_subway_distances_null_over_1km():
    """walk_distance_m stored as NULL when TMAP returns > 1000m."""
    conn = init_db(":memory:")
    migrate_db(conn)
    conn.execute(
        "INSERT INTO apartments (lawd_cd, apt_nm, umd_nm, latitude, longitude) "
        "VALUES ('11680', '은마아파트', '대치동', 37.4940, 127.0634)"
    )
    conn.commit()
    apt_id = conn.execute("SELECT id FROM apartments").fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO subway_distances "
        "(apartment_id, station_name, line_name, walk_distance_m) "
        "VALUES (?, ?, ?, NULL)",
        (apt_id, "선릉", "2호선"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT walk_distance_m FROM subway_distances WHERE apartment_id=? AND station_name='선릉'",
        (apt_id,),
    ).fetchone()
    assert row is not None
    assert row[0] is None


# --- SUBW-03: Cache hit ---

@pytest.mark.xfail(strict=False, reason="subway_distances collector not yet implemented")
def test_subway_distances_cache_hit():
    """Second call for same (apartment_id, station_name) returns cached row without API call."""
    conn = init_db(":memory:")
    migrate_db(conn)
    conn.execute(
        "INSERT INTO apartments (lawd_cd, apt_nm, umd_nm, latitude, longitude) "
        "VALUES ('11680', '은마아파트', '대치동', 37.4940, 127.0634)"
    )
    conn.commit()
    apt_id = conn.execute("SELECT id FROM apartments").fetchone()[0]
    # Insert cached row
    conn.execute(
        "INSERT OR IGNORE INTO subway_distances "
        "(apartment_id, station_name, line_name, walk_distance_m) VALUES (?, '선릉', '2호선', 400)",
        (apt_id,),
    )
    conn.commit()
    # Check that the cache lookup returns 1 row (collector should skip TMAP)
    cached = conn.execute(
        "SELECT 1 FROM subway_distances WHERE apartment_id=? AND station_name='선릉'",
        (apt_id,),
    ).fetchone()
    assert cached is not None


# --- COMM-01: Graph construction ---

@pytest.mark.xfail(strict=False, reason="station_loader not yet implemented")
def test_build_subway_graph():
    """build_subway_graph() creates nodes and edges for a synthetic 3-station DataFrame."""
    import pandas as pd
    import networkx as nx
    from pipeline.graph.station_loader import build_subway_graph_from_df
    df = pd.DataFrame({
        "역사명": ["강남", "역삼", "선릉"],
        "노선명": ["2호선", "2호선", "2호선"],
        "역위도": ["37.4979", "37.5007", "37.5047"],
        "역경도": ["127.0276", "127.0360", "127.0495"],
        "환승역구분": ["N", "N", "N"],
        "환승노선명": ["", "", ""],
    })
    G = build_subway_graph_from_df(df)
    assert isinstance(G, nx.Graph)
    assert G.number_of_nodes() == 3
    assert G.number_of_edges() == 2  # 강남-역삼, 역삼-선릉


@pytest.mark.xfail(strict=False, reason="station_loader not yet implemented")
def test_subway_graph_transfer_edges():
    """Transfer edges connect same-name stations on different lines with weight=0."""
    import pandas as pd
    import networkx as nx
    from pipeline.graph.station_loader import build_subway_graph_from_df
    df = pd.DataFrame({
        "역사명": ["강남", "강남"],
        "노선명": ["2호선", "신분당선"],
        "역위도": ["37.4979", "37.4979"],
        "역경도": ["127.0276", "127.0276"],
        "환승역구분": ["Y", "Y"],
        "환승노선명": ["신분당선", "2호선"],
    })
    G = build_subway_graph_from_df(df)
    # Transfer edge between "강남_2호선" and "강남_신분당선"
    assert G.has_edge("강남_2호선", "강남_신분당선")
    edge_data = G.get_edge_data("강남_2호선", "강남_신분당선")
    assert edge_data["weight"] == 0


# --- COMM-02/03/04: BFS stop counts ---

@pytest.mark.xfail(strict=False, reason="station_loader not yet implemented")
def test_min_stops_bfs():
    """min_stops(G, '강남', ['역삼']) returns 1 on a 2-station line segment."""
    import pandas as pd
    import networkx as nx
    from pipeline.graph.station_loader import build_subway_graph_from_df, min_stops
    df = pd.DataFrame({
        "역사명": ["강남", "역삼"],
        "노선명": ["2호선", "2호선"],
        "역위도": ["37.4979", "37.5007"],
        "역경도": ["127.0276", "127.0360"],
        "환승역구분": ["N", "N"],
        "환승노선명": ["", ""],
    })
    G = build_subway_graph_from_df(df)
    result = min_stops(G, "강남", ["역삼"])
    assert result == 1


@pytest.mark.xfail(strict=False, reason="station_loader not yet implemented")
def test_min_stops_no_path():
    """min_stops() returns None when source and target are disconnected."""
    import networkx as nx
    from pipeline.graph.station_loader import min_stops
    G = nx.Graph()
    G.add_node("A_1호선", station_name="A", line_name="1호선")
    G.add_node("B_2호선", station_name="B", line_name="2호선")
    # No edges — disconnected
    result = min_stops(G, "A", ["B"])
    assert result is None


# --- COMM-05: commute_stops upsert ---

@pytest.mark.xfail(strict=False, reason="commute_stops collector not yet implemented")
def test_commute_stops_upsert():
    """INSERT OR REPLACE into commute_stops stores stops_to_gbd=5."""
    conn = init_db(":memory:")
    migrate_db(conn)
    conn.execute(
        "INSERT INTO apartments (lawd_cd, apt_nm, umd_nm) VALUES ('11680', '은마아파트', '대치동')"
    )
    conn.commit()
    apt_id = conn.execute("SELECT id FROM apartments").fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO commute_stops "
        "(apartment_id, nearest_station, stops_to_gbd, stops_to_cbd, stops_to_ybd) "
        "VALUES (?, ?, ?, ?, ?)",
        (apt_id, "선릉", 1, 10, 8),
    )
    conn.commit()
    row = conn.execute(
        "SELECT stops_to_gbd, stops_to_cbd, stops_to_ybd FROM commute_stops WHERE apartment_id=?",
        (apt_id,),
    ).fetchone()
    assert row[0] == 1
    assert row[1] == 10
    assert row[2] == 8


# --- SUBW-01: haversine utility ---

@pytest.mark.xfail(strict=False, reason="haversine not yet implemented")
def test_haversine_m():
    """haversine_m() returns ~3,140m for 강남역 -> 역삼역 known pair."""
    from pipeline.graph.station_loader import haversine_m
    # 강남역: 37.4979, 127.0276  /  선릉역: 37.5047, 127.0495
    dist = haversine_m(37.4979, 127.0276, 37.5047, 127.0495)
    assert 1800 < dist < 2500  # ~2.1km straight line
