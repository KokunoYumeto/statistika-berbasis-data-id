#!/usr/bin/env python3
"""Bounded REST publication of the verified R011-B025 package.

Self-check and probe modes are offline.  Only explicit ``--publish`` reads one
destination credential.  Publication stays in the existing Zenodo concept and
GitHub repository, preflights collisions, and anonymously reads every byte back.
No local Git command or upstream-contact operation exists here.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import requests

from b025_pipeline_contract import (
    BOUNDARY_ID, CONFIG_PATH, GITHUB_TAG, MODEL, PRIOR_GITHUB_RECEIPT,
    PRIOR_ZENODO_RECEIPT, RELEASE_DIR, RELEASE_ID, ROOT, StageGateError,
    VERSION, canonical, identity, offline_self_check, repo_path,
)
from package_b025 import ASSETS, SOURCE_TOOLING, _source_rows, config, metadata, verify_package
from publish_b018 import (
    GitHubClient, ZenodoClient, ZENODO_API, _fixed_redirect_get,
    _git_blob_sha, _github_create_hierarchical_tree, _github_head, _github_tree,
    _is_sha1, _stream_sha, _zenodo_public_json, _zenodo_public_request,
    _zenodo_public_versions, token_from_file,
)


ZENODO_RECEIPT = ROOT / "qa/b025-publication" / f"ZENODO_PUBLICATION_RECEIPT_{RELEASE_ID}.json"
GITHUB_RECEIPT = RELEASE_DIR / "GITHUB_PUBLICATION_RECEIPT.json"
STATUSES = {"PUBLISHED_AND_ANONYMOUSLY_VERIFIED", "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED"}


def md5(path: Path) -> str:
    digest=hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()


def expected_assets() -> list[dict]:
    verify_package(); rows=[]
    for name in ASSETS:
        path=RELEASE_DIR/name; row=identity(path); rows.append({"filename":name,"bytes":row["bytes"],"sha256":row["sha256"],"md5":md5(path)})
    return rows


def _public_stream(url: str, hosts: set[str]) -> tuple[int,str]:
    session=requests.Session(); session.trust_env=False; session.headers["User-Agent"]="interlanguage-r011-b025-public-readback/1"
    response=_fixed_redirect_get(session,url,hosts=hosts,stream=True)
    if response.status_code!=200: raise StageGateError(f"anonymous download returned HTTP {response.status_code}")
    return _stream_sha(response)


def validate_metadata(value: dict, cfg: dict) -> dict:
    actual=value.get("metadata") if isinstance(value.get("metadata"),dict) else value
    expected=metadata(cfg)["metadata"]
    if isinstance(actual.get("license"),dict): actual=dict(actual); actual["license"]=actual["license"].get("id")
    checks={"title":actual.get("title")==expected["title"],"version":actual.get("version")==VERSION,"date":actual.get("publication_date")==cfg["release_date"],"license":actual.get("license")=="cc-by-sa-3.0","language":actual.get("language")=="ind","access":actual.get("access_right","open")=="open","model":MODEL in str(actual.get("description","")) and MODEL in str(actual.get("notes","")),"partial":"parsial" in str(actual.get("description","")).casefold(),"scope":"Bagian 6.4" in str(actual.get("description","")),"no_restricted":"tidak ada solusi instruktur terbatas" in str(actual.get("description","")).casefold()}
    failed=[key for key,value in checks.items() if not value]
    if failed: raise StageGateError(f"Zenodo metadata mismatch: {failed}")
    return actual


def zenodo_readback(record_id: int, expected: list[dict], cfg: dict) -> dict:
    record=_zenodo_public_json(f"{ZENODO_API}/records/{record_id}")
    if int(record.get("conceptrecid",-1))!=22059801 or record.get("doi")!=f"10.5281/zenodo.{record_id}": raise StageGateError("Zenodo record escaped existing concept")
    validate_metadata(record,cfg); files=record.get("files") or []; by={row.get("key"):row for row in files}
    if set(by)!={row["filename"] for row in expected}: raise StageGateError("Zenodo public inventory mismatch")
    verified=[]
    for wanted in expected:
        remote=by[wanted["filename"]]; link=remote.get("links",{}).get("self") or remote.get("links",{}).get("content")
        response=_zenodo_public_request(link,preload_content=False)
        if response.status!=200: response.release_conn(); raise StageGateError("Zenodo anonymous download failed")
        digest=hashlib.sha256(); count=0
        try:
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                count+=len(chunk); digest.update(chunk)
        finally: response.release_conn()
        if (count,digest.hexdigest())!=(wanted["bytes"],wanted["sha256"]): raise StageGateError(f"Zenodo byte mismatch: {wanted['filename']}")
        verified.append({"filename":wanted["filename"],"bytes":count,"sha256":digest.hexdigest()})
    return {"record":record,"files":verified}


def token(service: str) -> str:
    env_file=os.environ.get(f"INTERLANGUAGE_{service.upper()}_TOKEN_FILE")
    candidates=([Path(env_file)] if env_file else []) + ([Path.home()/"Documents/Obsidian notes/New zenodo token.md",Path.home()/"Downloads/Zenodo token.md"] if service=="zenodo" else [Path.home()/"Downloads/Github Tokens.md",Path.home()/"Documents/Obsidian notes/Github Tokens.md"])
    path=next((p for p in candidates if p.is_file()),None)
    if path is None: raise StageGateError(f"{service} credential file is absent")
    return token_from_file(path,service=service)


def write_receipt(path: Path, payload: dict) -> dict:
    path.parent.mkdir(parents=True,exist_ok=True); raw=canonical(payload); temporary=path.with_name(path.name+".b025.tmp")
    if temporary.exists(): raise StageGateError(f"stale publication-receipt temporary: {temporary}")
    temporary.write_bytes(raw); os.replace(temporary,path); return payload


def publish_zenodo() -> dict:
    cfg=config(); expected=expected_assets(); versions=_zenodo_public_versions(22059801); matches=[r for r in versions if r.get("metadata",{}).get("version")==VERSION]
    if len(matches)>1: raise StageGateError("multiple Zenodo B025 versions exist")
    if matches:
        rid=int(matches[0]["id"]); back=zenodo_readback(rid,expected,cfg); status="ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED"
    else:
        if not versions or int(versions[0].get("id",-1))!=PRIOR_ZENODO_RECEIPT["record_id"]: raise StageGateError("Zenodo public head is not pinned B024")
        client=ZenodoClient(token("zenodo")); prior_id=PRIOR_ZENODO_RECEIPT["record_id"]; prior=client.json("GET",f"{ZENODO_API}/deposit/depositions/{prior_id}")
        if int(prior.get("conceptrecid",-1))!=22059801 or prior.get("state")!="done": raise StageGateError("authenticated Zenodo predecessor changed")
        link=prior.get("links",{}).get("latest_draft"); draft=None
        if isinstance(link,str):
            candidate=client.json("GET",link)
            if int(candidate.get("id",prior_id))!=prior_id and candidate.get("submitted") is not True: draft=candidate
        if draft is None:
            created=client.json("POST",f"{ZENODO_API}/deposit/depositions/{prior_id}/actions/newversion",expected=(201,202)); link=created.get("links",{}).get("latest_draft")
            if not isinstance(link,str): raise StageGateError("Zenodo new version lacks draft")
            draft=client.json("GET",link)
        did=int(draft.get("id",-1)); bucket=draft.get("links",{}).get("bucket")
        if int(draft.get("conceptrecid",-1))!=22059801 or not isinstance(bucket,str) or not bucket.startswith("https://zenodo.org/api/files/"): raise StageGateError("Zenodo draft identity malformed")
        by={row.get("filename"):row for row in draft.get("files") or []}; wanted={row["filename"]:row for row in expected}
        for name,row in list(by.items()):
            match=wanted.get(name); checksum=str(row.get("checksum","")).removeprefix("md5:"); size=int(row.get("filesize",row.get("size",-1)))
            if match and (checksum,size)==(match["md5"],match["bytes"]): continue
            client.request("DELETE",f"{ZENODO_API}/deposit/depositions/{did}/files/{row['id']}",expected=(204,)); by.pop(name,None)
        for name in ASSETS:
            if name in by: continue
            with (RELEASE_DIR/name).open("rb") as source: client.request("PUT",bucket.rstrip("/")+"/"+quote(name,safe=""),expected=(200,201),data=source,headers={"Content-Type":"application/octet-stream"})
        meta=metadata(cfg); validate_metadata(meta,cfg); client.json("PUT",f"{ZENODO_API}/deposit/depositions/{did}",data=canonical(meta),headers={"Content-Type":"application/json"})
        draft=client.json("GET",f"{ZENODO_API}/deposit/depositions/{did}"); validate_metadata(draft,cfg); remote={row.get("filename"):row for row in draft.get("files") or []}
        if set(remote)!={row["filename"] for row in expected}: raise StageGateError("Zenodo draft inventory differs before publish")
        for wanted in expected:
            row=remote[wanted["filename"]]; checksum=str(row.get("checksum","")).removeprefix("md5:"); size=int(row.get("filesize",row.get("size",-1)))
            if (checksum,size)!=(wanted["md5"],wanted["bytes"]): raise StageGateError(f"Zenodo draft identity mismatch: {wanted['filename']}")
        if any(r.get("metadata",{}).get("version")==VERSION for r in _zenodo_public_versions(22059801)): raise StageGateError("Zenodo B025 appeared concurrently")
        published=client.json("POST",f"{ZENODO_API}/deposit/depositions/{did}/actions/publish",expected=(201,202)); rid=int(published.get("record_id",published.get("id",-1))); back=zenodo_readback(rid,expected,cfg); status="PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
    pages=cfg["coverage"]["learner_reader_pages"]
    receipt={"$schema":"r011-b025-zenodo-publication-receipt/v1","boundary_id":BOUNDARY_ID,"release_id":RELEASE_ID,"status":status,"concept_doi":"10.5281/zenodo.22059801","concept_record_id":22059801,"record_id":rid,"doi":f"10.5281/zenodo.{rid}","public_url":f"https://zenodo.org/records/{rid}","version":VERSION,"access_right":"open","license_id":"cc-by-sa-3.0","production_model":MODEL,"learner_reader_pages":pages,"through":cfg["coverage"]["through"],"exercise_ids":list(range(1,39)),"public_answer_ids":list(range(1,38,2)),"o001_gap_ids":list(range(2,39,2)),"untranslated_instructional_or_exercise_prose_pages":0,"source_closure_counted_as_learner_output":False,"ordered_files":back["files"],"metadata_exactly_verified":True,"collision_preflight_before_mutation":True,"anonymous_public_byte_readback":True,"credentials_recorded":False,"local_git_used":False,"upstream_contact":False}
    return write_receipt(ZENODO_RECEIPT,receipt)


def source_tree_values(cfg: dict, zenodo: dict) -> dict[str,bytes]:
    values={}
    def add(path:str,raw:bytes):
        pure=PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts: raise StageGateError("unsafe GitHub path")
        if path in values and values[path]!=raw: raise StageGateError("GitHub tree collision")
        values[path]=raw
    binding=json.loads(repo_path("qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json").read_text(encoding="utf-8")); manifest_path=repo_path(binding["post_build_outputs"]["source_manifest"]["path"])
    for rel,path in _source_rows(manifest_path,manifest_path.parent/"source-snapshot"): add("source/full-source-closure/"+rel,path.read_bytes())
    for path in SOURCE_TOOLING+("scripts/b025_pipeline_contract.py","scripts/bind_b025_postbuild.py","scripts/promote_b025_reader.py","scripts/compile_backend_b025.py","scripts/admit_backend_b025.py","scripts/prepare_b025_release.py","scripts/package_b025.py","scripts/publish_b025.py"): add(path,repo_path(path).read_bytes())
    backend=json.loads(repo_path("backend/exports/manifest.json").read_text(encoding="utf-8")); projection=[]
    for row in backend["files"]:
        if row["path"].startswith(("core/","locales/","schemas/","views/")):
            path=repo_path("backend/exports/"+row["path"]); add("backend/exports/"+row["path"],path.read_bytes()); projection.append({k:row[k] for k in ("path","bytes","sha256")})
    add("backend/exports/manifest.json",canonical({"$schema":"r011-b025-github-public-backend-projection/v1","boundary_id":BOUNDARY_ID,"release_id":RELEASE_ID,"reader":cfg["inputs"]["reader"],"scope":cfg["coverage"],"files":projection,"source_closure_counted_as_learner_output":False}))
    add(cfg["inputs"]["reader"]["path"],repo_path(cfg["inputs"]["reader"]["path"]).read_bytes())
    for role,row in {**binding["sealed_inputs"],**binding["post_build_outputs"]}.items():
        if role not in {"base_backend","candidate_pdf","candidate_text"}:
            add(row["path"],repo_path(row["path"]).read_bytes())
    for path in ("qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json","qa/b025-reader/R011-B025_READER_PROMOTION_RECEIPT.json","qa/b025-backend-admission/R011-B025_BACKEND_ADMISSION_RECEIPT.json","qa/b025-backend-admission/R011-B025_BACKEND_REPLAY.json"):
        add(path,repo_path(path).read_bytes())
    for name in ("RELEASE_INPUTS.json",*ASSETS[3:]): add((RELEASE_DIR/name).relative_to(ROOT).as_posix(),(RELEASE_DIR/name).read_bytes())
    readme=(RELEASE_DIR/"README_RELEASE.md").read_text(encoding="utf-8")+f"\n## Repositori publik\n\n- Zenodo: <{zenodo['public_url']}>\n"; add("README.md",readme.encode()); add("LICENSE.md",(RELEASE_DIR/"LICENSES_AND_ATTRIBUTION.md").read_bytes()); add("CITATION.cff",(RELEASE_DIR/"CITATION.cff").read_bytes())
    add("00_control/PUBLICATION_STATE_R011-B025.md",f"# Status publikasi R011-B025\n\nEdisi kerja parsial hingga Bab 6 Bagian 6.4; {cfg['coverage']['learner_reader_pages']} halaman; latihan 1–38; jawaban publik ganjil 1–37; kesenjangan O001 genap 2–38; nol halaman prosa pembelajar Inggris; korpus lengkap: tidak.\n\nZenodo: {zenodo['public_url']}\n\nModel: {MODEL}. Tidak ada kontak hulu.\n".encode())
    if sum(map(len,values.values()))>100_000_000: raise StageGateError("GitHub exact tree exceeds bounded 100MB limit")
    return values


def release_contract(cfg:dict,zenodo:dict)->dict:
    pages=cfg["coverage"]["learner_reader_pages"]
    return {"tag_name":GITHUB_TAG,"name":"R011-B025 — pembaca Bahasa Indonesia hingga Bagian 6.4","body":f"Rilis kerja parsial: pembaca bersih {pages} halaman hingga Bab 6 Bagian 6.4; latihan 1–38; jawaban publik ganjil 1–37; kesenjangan O001 genap 2–38; nol halaman prosa pembelajar Inggris. Korpus lengkap: tidak. Zenodo: {zenodo['public_url']}\n\nModel: {MODEL}. Tidak ada kontak hulu.","draft":False,"prerelease":True}


def github_readback(cfg:dict,release:dict,commit_sha:str,desired:dict[str,str],expected:list[dict],contract:dict)->dict:
    public=GitHubClient(None,"KokunoYumeto","statistika-berbasis-data-id"); actual=public.json("GET",f"releases/tags/{quote(GITHUB_TAG,safe='')}")
    for key in ("tag_name","name","body","draft","prerelease"):
        if actual.get(key)!=contract[key]: raise StageGateError(f"GitHub release metadata mismatch: {key}")
    tree_sha=public.json("GET",f"git/commits/{commit_sha}").get("tree",{}).get("sha"); tree=_github_tree(public,tree_sha)
    if set(tree)!=set(desired) or any(tree[p].get("sha")!=s for p,s in desired.items()): raise StageGateError("GitHub anonymous tree mismatch")
    assets={row.get("name"):row for row in actual.get("assets") or []}
    if set(assets)!={row["filename"] for row in expected}: raise StageGateError("GitHub asset inventory mismatch")
    verified=[]
    for wanted in expected:
        row=assets[wanted["filename"]]; count,digest=_public_stream(row["browser_download_url"],{"github.com","objects.githubusercontent.com","release-assets.githubusercontent.com"})
        if (count,digest)!=(wanted["bytes"],wanted["sha256"]): raise StageGateError(f"GitHub byte mismatch: {wanted['filename']}")
        verified.append({"filename":wanted["filename"],"bytes":count,"sha256":digest})
    return {"assets":verified,"tree_path_count":len(tree),"release":actual}


def publish_github() -> dict:
    cfg=config(); expected=expected_assets()
    if not ZENODO_RECEIPT.is_file(): raise StageGateError("verified B025 Zenodo receipt absent")
    zenodo=json.loads(ZENODO_RECEIPT.read_text(encoding="utf-8"))
    if zenodo.get("status") not in STATUSES or zenodo.get("access_right")!="open" or zenodo.get("anonymous_public_byte_readback") is not True: raise StageGateError("Zenodo receipt is not publication-authorizing")
    values=source_tree_values(cfg,zenodo); desired={p:_git_blob_sha(raw) for p,raw in values.items()}; contract=release_contract(cfg,zenodo); public=GitHubClient(None,"KokunoYumeto","statistika-berbasis-data-id")
    tag=public.maybe_json(f"git/ref/tags/{quote(GITHUB_TAG,safe='')}"); rel=public.maybe_json(f"releases/tags/{quote(GITHUB_TAG,safe='')}")
    if (tag is None)!=(rel is None): raise StageGateError("GitHub tag/release collision is partial")
    if tag is not None:
        commit_sha=tag.get("object",{}).get("sha"); back=github_readback(cfg,rel,commit_sha,desired,expected,contract); status="ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED"
    else:
        client=GitHubClient(token("github"),"KokunoYumeto","statistika-berbasis-data-id"); head,prior_tree=_github_head(client,"main")
        if head!=PRIOR_GITHUB_RECEIPT["commit"]:
            interrupted=client.json("GET",f"git/commits/{head}"); parents=interrupted.get("parents") or []; tree_sha=interrupted.get("tree",{}).get("sha"); observed=_github_tree(client,tree_sha)
            if len(parents)!=1 or parents[0].get("sha")!=PRIOR_GITHUB_RECEIPT["commit"] or set(observed)!=set(desired) or any(observed[p].get("sha")!=s for p,s in desired.items()): raise StageGateError("GitHub main is neither B024 nor the exact interrupted B025 tree")
            commit_sha=head
        else:
            known={row.get("sha") for row in _github_tree(client,prior_tree).values()}; created=set()
            for path,raw in values.items():
                digest=desired[path]
                if digest in known or digest in created: continue
                result=client.json("POST","git/blobs",expected=(201,),payload={"content":base64.b64encode(raw).decode(),"encoding":"base64"})
                if result.get("sha")!=digest: raise StageGateError(f"GitHub blob mismatch: {path}")
                created.add(digest)
            tree_sha=_github_create_hierarchical_tree(client,desired); commit=client.json("POST","git/commits",expected=(201,),payload={"message":"Preserve Indonesian R011-B025 reader through Section 6.4","tree":tree_sha,"parents":[head],"author":{"name":"Codex, atas permintaan pengguna","email":"codex@users.noreply.github.com"},"committer":{"name":"Codex, atas permintaan pengguna","email":"codex@users.noreply.github.com"}}); commit_sha=commit.get("sha")
            if not _is_sha1(commit_sha): raise StageGateError("GitHub commit lacks SHA")
            client.json("PATCH","git/refs/heads/main",payload={"sha":commit_sha,"force":False})
        client.json("POST","git/refs",expected=(201,),payload={"ref":f"refs/tags/{GITHUB_TAG}","sha":commit_sha}); create=dict(contract); create["target_commitish"]=commit_sha; rel=client.json("POST","releases",expected=(201,),payload=create)
        for wanted in expected:
            with (RELEASE_DIR/wanted["filename"]).open("rb") as source: client.request("POST",f"releases/{rel['id']}/assets?name={quote(wanted['filename'],safe='')}",expected=(201,),data=source,headers={"Content-Type":"application/octet-stream"},upload=True)
        back=github_readback(cfg,rel,commit_sha,desired,expected,contract); status="PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
    commit=public.json("GET",f"git/commits/{commit_sha}"); parents=commit.get("parents") or []
    if len(parents)!=1 or parents[0].get("sha")!=PRIOR_GITHUB_RECEIPT["commit"]: raise StageGateError("GitHub B025 commit parent changed")
    receipt={"$schema":"r011-b025-github-publication-receipt/v1","boundary_id":BOUNDARY_ID,"release_id":RELEASE_ID,"status":status,"repository":"KokunoYumeto/statistika-berbasis-data-id","repository_public":True,"tag":GITHUB_TAG,"release_id_numeric":int(back["release"]["id"]),"release_url":back["release"].get("html_url"),"parent_commit":PRIOR_GITHUB_RECEIPT["commit"],"release_commit":commit_sha,"tree_path_count":back["tree_path_count"],"ordered_assets":back["assets"],"zenodo_public_url":zenodo["public_url"],"learner_reader_pages":cfg["coverage"]["learner_reader_pages"],"through":cfg["coverage"]["through"],"untranslated_instructional_or_exercise_prose_pages":0,"source_closure_counted_as_learner_output":False,"production_model":MODEL,"collision_preflight_before_mutation":True,"anonymous_exact_tree_readback":True,"anonymous_public_byte_readback":True,"credentials_recorded":False,"local_git_used":False,"upstream_contact":False}
    return write_receipt(GITHUB_RECEIPT,receipt)


def main(destination:str|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("destination",nargs="?",choices=("zenodo","github"),default=destination); mode=parser.add_mutually_exclusive_group(required=True); mode.add_argument("--self-check",action="store_true"); mode.add_argument("--probe",action="store_true"); mode.add_argument("--publish",action="store_true"); args=parser.parse_args()
    if args.destination is None: parser.error("destination is required")
    if args.self_check: result=offline_self_check(f"b025-{args.destination}-publisher")
    elif args.probe: cfg=config(); verify_package(); result={"status":"PASS_B025_PUBLICATION_PROBE_OFFLINE_NO_WRITES","destination":args.destination,"config":identity(CONFIG_PATH),"assets":expected_assets(),"network_used":False,"credentials_accessed":False,"writes_performed":False}
    else: result=publish_zenodo() if args.destination=="zenodo" else publish_github()
    print(json.dumps(result,ensure_ascii=False,sort_keys=True)); return 0


if __name__=="__main__":
    try: raise SystemExit(main())
    except StageGateError as exc: raise SystemExit(f"REFUSED: {exc}")
