"""Read-only checks on fictional inputs and saved audit evidence."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.stocks import history_audit
from src.stocks.history_audit import check_saved, file_hashes, run
from src.stocks.pull import sha256
from tests.stocks.test_history_audit import END, START, EvidenceDB, fixture_data


def forbid_io_writes_and_queries(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only check attempted a write, build, run or query')

    monkeypatch.setattr('src.stocks.history_audit.fetch_evidence', forbidden)
    monkeypatch.setattr('src.stocks.history_audit.run', forbidden)
    monkeypatch.setattr('src.stocks.build.build', forbidden)
    monkeypatch.setattr('src.stocks.pull.pull', forbidden)
    monkeypatch.setattr('src.stocks.pull.connect', forbidden)
    monkeypatch.setattr('src.common.wrds_conn.connect', forbidden)
    original_open = Path.open

    def read_only_open(self, mode='r', *args, **kwargs):
        if any(flag in mode for flag in 'wax+'):
            forbidden()
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', read_only_open)
    for name in ['mkdir', 'write_text', 'write_bytes', 'unlink', 'rename', 'replace']:
        monkeypatch.setattr(Path, name, forbidden)


@pytest.mark.parametrize('with_evidence', [False, True])
def test_check_saved_has_no_writes_or_connections(tmp_path, monkeypatch, with_evidence):
    fixture_data(tmp_path)
    evidence = None
    if with_evidence:
        evidence, _ = run(tmp_path, START, END, 'saved', connect_factory=EvidenceDB)
    before = file_hashes(tmp_path)
    forbid_io_writes_and_queries(monkeypatch)
    result = check_saved(tmp_path, START, END, evidence)
    assert result['input_check'] == 'pass'
    assert result['files_written'] is False and result['connection_opened'] is False
    assert result['saved_files_unchanged'] is True
    assert result['evidence_check'] == ('pass' if with_evidence else 'not_requested')
    if with_evidence:
        assert result['csv_tables_compared'] == 8
    assert file_hashes(tmp_path) == before


@pytest.mark.parametrize('rewrite_manifest_hash', [False, True])
def test_changed_saved_output_is_detected_without_repair(tmp_path, rewrite_manifest_hash):
    fixture_data(tmp_path)
    evidence, _ = run(tmp_path, START, END, 'saved', connect_factory=EvidenceDB)
    table = evidence / 'quote_sensitivity.csv'
    frame = pd.read_csv(table)
    frame.loc[0, 'mean_main_bps'] += 1
    frame.to_csv(table, index=False)
    if rewrite_manifest_hash:
        manifest_path = evidence / 'audit_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['outputs'][table.name]['sha256'] = sha256(table)
        manifest_path.write_text(json.dumps(manifest))
    before = file_hashes(tmp_path)
    with pytest.raises((ValueError, AssertionError)):
        check_saved(tmp_path, START, END, evidence)
    assert file_hashes(tmp_path) == before


def test_saved_audit_with_different_raw_manifest_is_rejected(tmp_path):
    fixture_data(tmp_path)
    evidence, _ = run(tmp_path, START, END, 'saved', connect_factory=EvidenceDB)
    path = evidence / 'audit_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['raw_manifest_sha256'] = '0' * 64
    path.write_text(json.dumps(manifest), encoding='utf-8')
    before = file_hashes(tmp_path)
    with pytest.raises(ValueError, match='different raw manifest'):
        check_saved(tmp_path, START, END, evidence)
    assert file_hashes(tmp_path) == before


def test_ad_hoc_or_wrong_window_evidence_is_not_recertified(tmp_path):
    processed = fixture_data(tmp_path)
    before = file_hashes(tmp_path)
    with pytest.raises(ValueError, match='completed run inside'):
        check_saved(tmp_path, START, END, processed / 'calendar_audit_v1')
    assert file_hashes(tmp_path) == before


def test_cli_check_only_compares_evidence_without_running_audit(tmp_path, monkeypatch, capsys):
    fixture_data(tmp_path)
    evidence, _ = run(tmp_path, START, END, 'saved', connect_factory=EvidenceDB)
    before = file_hashes(tmp_path)
    forbid_io_writes_and_queries(monkeypatch)
    monkeypatch.setattr('sys.argv', [
        'history_audit', '--data-root', str(tmp_path), '--start', START,
        '--end', END, '--check-only', '--evidence-dir', str(evidence),
    ])
    history_audit.main()
    result = json.loads(capsys.readouterr().out)
    assert result['evidence_check'] == 'pass' and result['csv_tables_compared'] == 8
    assert file_hashes(tmp_path) == before
