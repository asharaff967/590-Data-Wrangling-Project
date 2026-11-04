"""Fictional raw-run corruption must stop both stock consumers."""
import json

import pandas as pd
import pytest

from src.stocks.build import build
from src.stocks.history_audit import load_inputs
from src.stocks.pull import raw_folder
from src.stocks.raw_inputs import daily_source_rows
from tests.stocks.test_history_audit import END, START, fixture_data


@pytest.mark.parametrize('problem', ['incomplete', 'wrong_window', 'missing_file', 'duplicate_file', 'row_count'])
def test_manifest_corruption_stops_build_and_history_audit(tmp_path, problem):
    fixture_data(tmp_path)
    path = raw_folder(tmp_path, START, END) / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if problem == 'incomplete':
        manifest['status'] = 'incomplete'
    elif problem == 'wrong_window':
        manifest['end'] = '2020-12-23'
    elif problem == 'missing_file':
        manifest['files'].pop()
    elif problem == 'duplicate_file':
        manifest['files'].append(manifest['files'][0])
    else:
        manifest['files'][0]['rows'] += 1
    path.write_text(json.dumps(manifest), encoding='utf-8')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    for consumer in [build, load_inputs]:
        with pytest.raises(ValueError):
            consumer(tmp_path, START, END)
    assert all(path.read_bytes() == value for path, value in before.items())


def test_multiple_year_files_keep_original_order_and_csv_line_provenance():
    frames = {
        'daily_2021.csv': pd.DataFrame({'permno': [1], 'date': ['2021-01-04']}),
        'daily_2020.csv': pd.DataFrame({'permno': [1, 2], 'date': ['2020-12-31'] * 2}),
    }
    before = {name: frame.copy(deep=True) for name, frame in frames.items()}
    result = daily_source_rows(frames, '2020-12-31', '2021-01-04')
    assert result['permno'].tolist() == [1, 2, 1]
    assert result['source_file'].tolist() == ['daily_2020.csv', 'daily_2020.csv', 'daily_2021.csv']
    assert result['source_row'].tolist() == [2, 3, 2]
    for name, frame in frames.items():
        pd.testing.assert_frame_equal(frame, before[name])
