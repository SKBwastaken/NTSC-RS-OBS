use std::{env, fs, path::PathBuf, process::Command};

fn main() {
    assert_eq!(env::var("CARGO_CFG_TARGET_OS").unwrap(), "windows");
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    let obs = PathBuf::from(
        env::var_os("OBS_DIR").unwrap_or_else(|| r"C:\Program Files\obs-studio".into()),
    );
    println!("cargo:rerun-if-env-changed=OBS_DIR");
    println!("cargo:rerun-if-changed=native/filter.c");
    println!("cargo:rerun-if-changed=native/bridge.h");
    fs::write(
        out.join("obsconfig.h"),
        "#pragma once\n#define OBS_RELEASE_CANDIDATE 0\n#define OBS_BETA 0\n",
    )
    .unwrap();
    let mut build = cc::Build::new();
    build
        .file("native/filter.c")
        .include("vendor/obs-studio/libobs")
        .include(&out)
        .define("WIN32_LEAN_AND_MEAN", None)
        .flag("/std:c11")
        .flag("/experimental:c11atomics")
        .flag("/utf-8");
    let compiler = build.get_compiler();
    let bin = compiler.path().parent().unwrap();
    let exports = Command::new(bin.join("dumpbin.exe"))
        .arg("/nologo")
        .arg("/exports")
        .arg(obs.join("bin/64bit/obs.dll"))
        .output()
        .expect("dumpbin.exe");
    assert!(exports.status.success(), "OBS DLL export scan failed");
    let mut def = String::from("LIBRARY obs.dll\nEXPORTS\n");
    for line in String::from_utf8_lossy(&exports.stdout).lines() {
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.len() >= 4
            && fields[0].parse::<u32>().is_ok()
            && u32::from_str_radix(fields[1], 16).is_ok()
            && u64::from_str_radix(fields[2], 16).is_ok()
        {
            def.push_str(fields[3]);
            def.push('\n');
        }
    }
    assert!(def.lines().count() > 100, "No OBS exports found");
    fs::write(out.join("obs.def"), def).unwrap();
    let status = Command::new(bin.join("lib.exe"))
        .arg("/nologo")
        .arg("/machine:x64")
        .arg(format!("/def:{}", out.join("obs.def").display()))
        .arg(format!("/out:{}", out.join("obs.lib").display()))
        .status()
        .unwrap();
    assert!(status.success(), "Import library generation failed");
    build.compile("ntsc_obs_bridge");
    println!("cargo:rustc-link-search=native={}", out.display());
    println!("cargo:rustc-link-lib=dylib=obs");
}
