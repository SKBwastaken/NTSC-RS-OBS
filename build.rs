use std::{env, fs, path::PathBuf, process::Command};

fn main() {
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap();
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    println!("cargo:rerun-if-env-changed=OBS_DIR");
    println!("cargo:rerun-if-env-changed=OBS_LIB_DIR");
    println!("cargo:rerun-if-env-changed=OBS_INCLUDE_DIR");
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
        .include(
            env::var_os("OBS_INCLUDE_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| PathBuf::from("vendor/obs-studio/libobs")),
        )
        .include(&out)
        .define(
            "NTSC_RS_OBS_VERSION",
            format!("\"{}\"", env::var("CARGO_PKG_VERSION").unwrap()).as_str(),
        );
    match target_os.as_str() {
        "windows" => windows(build, &out),
        "linux" => linux(build),
        other => panic!("Unsupported target OS: {other}"),
    }
}

fn windows(mut build: cc::Build, out: &std::path::Path) {
    let obs = PathBuf::from(
        env::var_os("OBS_DIR").unwrap_or_else(|| r"C:\Program Files\obs-studio".into()),
    );
    build
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

fn linux(mut build: cc::Build) {
    build.flag("-std=gnu11");
    build.compile("ntsc_obs_bridge");
    if let Some(dir) = env::var_os("OBS_LIB_DIR") {
        println!(
            "cargo:rustc-link-search=native={}",
            PathBuf::from(dir).display()
        );
    }
    // Distribution OBS packages ship the runtime SONAME, not always the
    // unversioned development symlink.
    println!("cargo:rustc-link-lib=dylib:+verbatim=libobs.so.0");
}
