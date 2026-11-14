"""Interrupted publication proof uses disposable bytes and a killed child process."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest
from glowforge_it import publication


def interrupted(tmp_path, *, previous=True):
    destinations = [tmp_path / 'one.png', tmp_path / 'two.svg']
    for path, raw in zip(destinations, [b'old-one', b'old-two']):
        if previous:
            path.write_bytes(raw)
    staged = [Path(publication.stage_beside(path, lambda name, raw=raw: Path(name).write_bytes(raw)))
              for path, raw in zip(destinations, [b'new-one', b'new-two'])]
    code = '''import os,sys,json
from glowforge_it import publication
pairs=json.loads(sys.argv[1])
real=os.replace
def replace(source,destination):
    if str(source)==pairs[1][1]: os._exit(77)
    return real(source,destination)
publication.os.replace=replace
publication.publish_generation(pairs)
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in ['OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ELEVENLABS_API_KEY']:
        env.pop(key, None)
    result = subprocess.run([sys.executable, '-B', '-c', code, json.dumps([[str(d), str(s)] for d,s in zip(destinations,staged)])],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 77, result.stderr
    journals=list(tmp_path.glob('.gf-publish-*.json'))
    assert len(journals)==1
    return destinations, journals[0]


def test_hard_process_exit_leaves_a_named_exact_recovery_route(tmp_path):
    destinations, journal=interrupted(tmp_path)
    assert destinations[0].read_bytes()==b'new-one'
    assert not destinations[1].exists()
    before={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    inspection=publication.recover_publication(journal,dry_run=True)
    assert [x['action'] for x in inspection['actions']]==['restore','restore']
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}==before
    result=publication.recover_publication(journal)
    assert result['restored']
    assert [p.read_bytes() for p in destinations]==[b'old-one',b'old-two']
    assert not journal.exists() and not list(tmp_path.glob('.gf-prev-*'))


def test_recovery_refuses_a_later_user_edit_before_changing_any_destination(tmp_path):
    destinations,journal=interrupted(tmp_path)
    destinations[1].write_bytes(b'later owner work')
    with pytest.raises(publication.RecoveryError,match='changed after interruption'):
        publication.recover_publication(journal)
    assert destinations[0].read_bytes()==b'new-one'
    assert destinations[1].read_bytes()==b'later owner work'
    assert journal.exists()


def test_interrupted_new_generation_restores_the_previous_absence(tmp_path):
    destinations,journal=interrupted(tmp_path,previous=False)
    publication.recover_publication(journal)
    assert not any(p.exists() for p in destinations)


def test_unresolved_journal_blocks_another_overwrite(tmp_path):
    destinations,journal=interrupted(tmp_path)
    staged=publication.stage_beside(destinations[0],lambda name:Path(name).write_bytes(b'another attempt'))
    with pytest.raises(publication.RecoveryError,match='needs review first') as exc:
        publication.publish_generation([(destinations[0],staged)])
    assert exc.value.journal_path==str(journal)
    assert destinations[0].read_bytes()==b'new-one'


def test_committed_cleanup_warning_can_be_cleared_without_rolling_back(tmp_path,monkeypatch):
    dest=tmp_path/'one.png'; dest.write_bytes(b'old')
    staged=publication.stage_beside(dest,lambda name:Path(name).write_bytes(b'accepted'))
    real=os.unlink
    def unlink(path):
        if Path(path).name.startswith('.gf-prev-'):
            raise OSError('synthetic cleanup refusal')
        return real(path)
    monkeypatch.setattr(publication.os,'unlink',unlink)
    warnings=publication.publish_generation([(dest,staged)])
    assert warnings and dest.read_bytes()==b'accepted'
    journal=next(tmp_path.glob('.gf-publish-*.json'))
    monkeypatch.undo()
    result=publication.recover_publication(journal)
    assert result['cleaned_committed'] and not result['restored']
    assert dest.read_bytes()==b'accepted'
    assert not journal.exists()


def test_recovery_refuses_a_replaced_symlink_destination(tmp_path):
    destinations,journal=interrupted(tmp_path)
    destinations[0].unlink()
    untouched=tmp_path/'owner.txt'; untouched.write_bytes(b'owner')
    destinations[0].symlink_to(untouched)
    with pytest.raises(ValueError,match='symlink'):
        publication.recover_publication(journal)
    assert untouched.read_bytes()==b'owner'


def test_recovery_cleans_unused_backup_reservations_when_nothing_moved(tmp_path):
    dest=tmp_path/'one.png'; dest.write_bytes(b'old')
    backup=tmp_path/'.gf-prev-reserved'; backup.write_bytes(b'')
    journal=tmp_path/'.gf-publish-fixture.json'
    journal.write_text(json.dumps({'kind':'glowforge-publication','version':1,'state':'publishing','files':[
        {'destination':str(dest),'backup':str(backup),'old_sha256':hashlib.sha256(b'old').hexdigest(),
         'new_sha256':hashlib.sha256(b'new').hexdigest()}]}))
    publication.recover_publication(journal)
    assert dest.read_bytes()==b'old' and not backup.exists() and not journal.exists()


def test_recovery_cli_previews_then_restores_without_rendering(tmp_path,capsys):
    from glowforge_it.cli import gf_main
    destinations,journal=interrupted(tmp_path)
    assert gf_main(['--recover-publication',str(journal),'--dry-run','--json'])==0
    preview=json.loads(capsys.readouterr().out)
    assert preview['success'] and preview['recovery']['dry_run']
    assert destinations[0].read_bytes()==b'new-one'
    assert gf_main(['--recover-publication',str(journal),'--json'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['success'] and result['recovery']['restored']
    assert [p.read_bytes() for p in destinations]==[b'old-one',b'old-two']


def test_invalid_recovery_cli_is_a_structured_failure_not_a_render(tmp_path,capsys):
    from glowforge_it.cli import gf_main
    journal=tmp_path/'not-a-journal.json'; journal.write_text('{}')
    assert gf_main(['--recover-publication',str(journal),'--json'])==1
    result=json.loads(capsys.readouterr().out)
    assert not result['success'] and result['errors']
    assert list(tmp_path.iterdir())==[journal]


def test_exit_before_initial_journal_rename_leaves_retry_available(tmp_path):
    destination = tmp_path / 'one.png'
    destination.write_bytes(b'old')
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    code = """
import os
import sys

from glowforge_it import publication

real_replace = os.replace
def interrupt(source, destination):
    if os.path.basename(destination).startswith('.gf-publish-'):
        os._exit(77)
    real_replace(source, destination)

publication.os.replace = interrupt
publication.publish_generation([(sys.argv[1], sys.argv[2])])
"""
    child = subprocess.run([sys.executable, '-B', '-c', code, str(destination), staged],
                           capture_output=True, text=True, timeout=10)
    assert child.returncode == 77, child.stderr
    assert destination.read_bytes() == b'old'
    assert publication.pending_publication(tmp_path) is None
    assert publication.publish_generation([(destination, staged)]) == []
    assert destination.read_bytes() == b'new'


def test_publication_scans_directory_names_literally_and_quotes_recovery_path(tmp_path):
    directory = tmp_path / "proof [1] and it's ready"
    directory.mkdir()
    journal = directory / '.gf-publish-interrupted.json'
    journal.write_text('{}')
    with pytest.raises(publication.RecoveryError) as error:
        publication.check_pending_publication(directory)
    assert error.value.journal_path == str(journal)
    suggested = str(error.value).partition('Inspect with ')[2]
    assert shlex.split(suggested) == ['gf', '--recover-publication', str(journal), '--dry-run']
    assert publication.pending_publication(tmp_path / 'not created') is None


@pytest.mark.skipif(os.name != 'posix', reason='POSIX symlink and advisory lock semantics')
def test_canonical_parent_alias_works_but_cannot_redirect_staged_outputs(tmp_path):
    directory, other, alias = [tmp_path / name for name in ('real', 'other', 'alias')]
    directory.mkdir()
    other.mkdir()
    alias.symlink_to(directory, target_is_directory=True)
    destination = alias / 'output.png'
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    assert publication.publish_generation([(destination, staged)]) == []
    assert (directory / destination.name).read_bytes() == b'new'

    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'redirected'))
    alias.unlink()
    alias.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match='job directory'):
        publication.publish_generation([(destination, staged)])
    assert not (other / destination.name).exists()
    assert (directory / destination.name).read_bytes() == b'new'


@pytest.mark.parametrize('path_kind', ['outside', 'hardlink', 'traversal'])
def test_recovery_rejects_invalid_scope_or_alias_before_removing_artifacts(tmp_path, path_kind):
    directory = tmp_path / 'job'
    directory.mkdir()
    first = directory / 'first.png'
    first.write_bytes(b'first')
    second = tmp_path / 'unrelated.png'
    second.write_bytes(b'second')
    if path_kind == 'hardlink':
        second = directory / 'alias.png'
        os.link(first, second)
    elif path_kind == 'traversal':
        second = directory / '..' / second.name
    journal = directory / '.gf-publish-fixture.json'
    entries = [{'destination': str(path), 'backup': None, 'old_sha256': None,
                'new_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in (first, second)]
    journal.write_text(json.dumps({'kind': 'glowforge-publication', 'version': 1,
                                   'state': 'publishing', 'files': entries}))
    with pytest.raises(ValueError, match='job directory|distinct|Invalid publication path'):
        publication.recover_publication(journal)
    assert first.exists() and second.exists() and journal.exists()


def test_backup_cleanup_conflict_is_visible_in_dry_run_before_restoration(tmp_path):
    destinations, journal = interrupted(tmp_path)
    record = json.loads(journal.read_text())
    destinations[1].write_bytes(b'old-two')
    backup = Path(record['files'][1]['backup'])
    backup.write_bytes(b'owner edit')
    for dry_run in (True, False):
        with pytest.raises(publication.RecoveryError, match='previous bytes are missing or changed'):
            publication.recover_publication(journal, dry_run=dry_run)
    assert destinations[0].read_bytes() == b'new-one'
    assert backup.read_bytes() == b'owner edit'
    assert journal.exists()


def test_successful_recovery_removes_owned_staging_files_only(tmp_path):
    destinations, journal = interrupted(tmp_path)
    staged = list(tmp_path.glob('.gf-stage-*'))
    assert staged
    unrelated = tmp_path / '.gf-stage-unrelated.png'
    unrelated.write_bytes(b'keep')
    publication.recover_publication(journal)
    assert all(not path.exists() for path in staged)
    assert unrelated.read_bytes() == b'keep'
    assert [path.read_bytes() for path in destinations] == [b'old-one', b'old-two']


def test_journal_only_cleanup_warning_remains_a_successful_write(tmp_path, monkeypatch):
    destination = tmp_path / 'one.png'
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    real_unlink = os.unlink

    def fail_unlink(path):
        if Path(path).name.startswith('.gf-publish-'):
            raise PermissionError('synthetic journal cleanup refusal')
        real_unlink(path)

    monkeypatch.setattr(publication.os, 'unlink', fail_unlink)
    warnings = publication.publish_generation([(destination, staged)])
    journal = next(tmp_path.glob('.gf-publish-*.json'))
    assert warnings == [{'destination': None, 'backup': None, 'journal': str(journal),
                         'message': 'synthetic journal cleanup refusal'}]
    assert 'published successfully' in publication.format_cleanup_warning(warnings[0])
    assert destination.read_bytes() == b'new'
    monkeypatch.undo()
    assert publication.recover_publication(journal)['cleaned_committed']
    assert destination.read_bytes() == b'new'


@pytest.mark.skipif(os.name != 'posix', reason='POSIX directory advisory lock')
def test_recovery_refuses_to_interfere_with_live_publisher(tmp_path, monkeypatch):
    destination = tmp_path / 'one.png'
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    write = publication._write_journal
    live_checks = []

    def inspect_while_writing(path, record):
        write(path, record)
        if record['state'] == 'publishing':
            for dry_run in (True, False):
                with pytest.raises(publication.RecoveryError, match='is active'):
                    publication.recover_publication(path, dry_run=dry_run)
                live_checks.append(dry_run)

    monkeypatch.setattr(publication, '_write_journal', inspect_while_writing)
    assert publication.publish_generation([(destination, staged)]) == []
    assert live_checks == [True, False]
    assert destination.read_bytes() == b'new'


def test_publication_checks_absent_companion_under_lock(tmp_path):
    destination = tmp_path / 'output.png'
    destination.write_bytes(b'old')
    manifest = tmp_path / 'output_manifest.json'
    manifest.write_bytes(b'old metadata')
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    with pytest.raises(publication.RecoveryError, match='outdated companion'):
        publication.publish_generation([(destination, staged)], must_be_absent=[manifest])
    assert destination.read_bytes() == b'old'
    assert manifest.read_bytes() == b'old metadata'
    assert publication.pending_publication(tmp_path) is None


@pytest.mark.parametrize('interrupt_at', ['artifact', 'commit_record'])
def test_interrupt_after_rename_preserves_the_generation_named_by_the_journal(tmp_path, monkeypatch, interrupt_at):
    destination = tmp_path / 'one.png'
    destination.write_bytes(b'old')
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    real_replace = os.replace

    def interrupt_after_rename(source, target):
        real_replace(source, target)
        if interrupt_at == 'artifact' and source == staged:
            raise KeyboardInterrupt
        if (interrupt_at == 'commit_record' and Path(target).name.startswith('.gf-publish-')
                and json.loads(Path(target).read_text())['state'] == 'committed'):
            raise KeyboardInterrupt

    monkeypatch.setattr(publication.os, 'replace', interrupt_after_rename)
    with pytest.raises(KeyboardInterrupt):
        publication.publish_generation([(destination, staged)])
    monkeypatch.undo()
    journal = publication.pending_publication(tmp_path)
    if interrupt_at == 'artifact':
        assert journal is None
        assert destination.read_bytes() == b'old'
    else:
        assert publication.recover_publication(journal)['cleaned_committed']
        assert destination.read_bytes() == b'new'


def test_recovery_verifies_staged_copy_before_installing_restored_bytes(tmp_path, monkeypatch):
    destinations, journal = interrupted(tmp_path)
    copy = publication.shutil.copy2

    def corrupt_staged_copy(backup, staged):
        copy(backup, staged)
        Path(staged).write_bytes(b'wrong bytes')

    monkeypatch.setattr(publication.shutil, 'copy2', corrupt_staged_copy)
    with pytest.raises(publication.RecoveryError, match='changed during publication or recovery'):
        publication.recover_publication(journal)
    assert destinations[0].read_bytes() == b'new-one'
    assert not destinations[1].exists()
    assert journal.exists()


def test_post_commit_exception_does_not_report_a_failed_publication(tmp_path, monkeypatch):
    destination = tmp_path / 'one.png'
    destination.write_bytes(b'old')
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    real_replace = os.replace

    def fail_after_commit(source, target):
        real_replace(source, target)
        if (Path(target).name.startswith('.gf-publish-')
                and json.loads(Path(target).read_text())['state'] == 'committed'):
            raise OSError('synthetic failure after the atomic commit')

    monkeypatch.setattr(publication.os, 'replace', fail_after_commit)
    assert publication.publish_generation([(destination, staged)]) == []
    assert publication.pending_publication(tmp_path) is None
    assert destination.read_bytes() == b'new'


def test_committed_cleanup_preserves_a_changed_journal_and_its_backup(tmp_path, monkeypatch):
    destination = tmp_path / 'one.png'
    destination.write_bytes(b'old')
    staged = publication.stage_beside(destination, lambda path: Path(path).write_bytes(b'new'))
    real_write = publication._write_journal

    def write_then_change(path, record):
        real_write(path, record)
        if record['state'] == 'committed':
            Path(path).write_bytes(b'owner edit')

    monkeypatch.setattr(publication, '_write_journal', write_then_change)
    warnings = publication.publish_generation([(destination, staged)])
    assert len(warnings) == 1 and 'changed' in warnings[0]['message']
    assert Path(warnings[0]['journal']).read_bytes() == b'owner edit'
    assert next(tmp_path.glob('.gf-prev-*')).read_bytes() == b'old'
    assert destination.read_bytes() == b'new'


@pytest.mark.parametrize('change', ['remove', 'edit'])
def test_committed_recovery_preserves_backups_when_a_published_artifact_changes(tmp_path, monkeypatch, change):
    destinations = [tmp_path / name for name in ('first.png', 'second.svg')]
    for destination in destinations:
        destination.write_bytes(b'old')
    staged = [publication.stage_beside(path, lambda name: Path(name).write_bytes(b'new'))
              for path in destinations]
    real_unlink = os.unlink

    def keep_backups(path):
        if Path(path).name.startswith('.gf-prev-'):
            raise PermissionError('synthetic cleanup refusal')
        real_unlink(path)

    monkeypatch.setattr(publication.os, 'unlink', keep_backups)
    warnings = publication.publish_generation(zip(destinations, staged))
    assert len(warnings) == 2
    monkeypatch.undo()

    journal = next(tmp_path.glob('.gf-publish-*.json'))
    backups = list(tmp_path.glob('.gf-prev-*'))
    if change == 'remove':
        destinations[1].unlink()
    else:
        destinations[1].write_bytes(b'owner edit')
    for dry_run in (True, False):
        with pytest.raises(publication.RecoveryError, match='committed artifact.*missing or changed'):
            publication.recover_publication(journal, dry_run=dry_run)
    assert journal.exists()
    assert [path.read_bytes() for path in backups] == [b'old', b'old']
    assert destinations[0].read_bytes() == b'new'
    if change == 'remove':
        assert not destinations[1].exists()
    else:
        assert destinations[1].read_bytes() == b'owner edit'


def test_committed_cleanup_preflights_all_published_artifacts_before_removing_backups(tmp_path, monkeypatch):
    destinations = [tmp_path / name for name in ('first.png', 'second.svg')]
    for destination in destinations:
        destination.write_bytes(b'old')
    staged = [publication.stage_beside(path, lambda name: Path(name).write_bytes(b'new'))
              for path in destinations]
    real_write = publication._write_journal

    def write_then_change(path, record):
        real_write(path, record)
        if record['state'] == 'committed':
            destinations[1].unlink()

    monkeypatch.setattr(publication, '_write_journal', write_then_change)
    warnings = publication.publish_generation(zip(destinations, staged))
    assert len(warnings) == 1 and 'committed artifact' in warnings[0]['message']
    assert Path(warnings[0]['journal']).exists()
    assert [path.read_bytes() for path in tmp_path.glob('.gf-prev-*')] == [b'old', b'old']
    assert destinations[0].read_bytes() == b'new'
    assert not destinations[1].exists()


def test_planned_new_destination_is_protected_if_it_appears_before_publication(tmp_path):
    destination = tmp_path / 'art.png'
    staged = publication.stage_beside(destination, lambda name: Path(name).write_bytes(b'ours'))
    destination.write_bytes(b'published by another job')
    with pytest.raises(FileExistsError, match='Output appeared after planning'):
        publication.publish_generation([(destination, staged)], must_be_absent=(destination,))
    assert destination.read_bytes() == b'published by another job'
    assert publication.pending_publication(tmp_path) is None
