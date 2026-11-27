//! Guarda de sessão do agente (antes AgentSessionGuard.java): bloqueia ações recusadas
//! e interrompe ciclos, ecrãs vazios ou estagnados.
use crate::policy::{label_of, norm, Node};
use jni::objects::{JClass, JIntArray, JObjectArray, JString};
use jni::sys::{jboolean, jint, jlong, jstring};
use jni::JNIEnv;
use std::collections::HashSet;

const MAX_EMPTY_TREES: i32 = 3;
const MAX_CONSECUTIVE_EXEC_FAILURES: i32 = 3;
const MAX_STAGNANT_STEPS: i32 = 4;

#[derive(Debug, PartialEq)]
pub enum Verdict {
    Ok,
    Skip(String),
    Abort(&'static str, String),
}

#[derive(Default)]
pub struct Guard {
    refused_signatures: HashSet<String>,
    refused_spatial: HashSet<String>,
    refused_packages: HashSet<String>,
    refused_labels: HashSet<String>,
    ask_user_refusals: i32,
    empty_tree_streak: i32,
    consecutive_exec_failures: i32,
    stagnant_steps: i32,
    last_screen_hash: i64,
    last_action_sig: String,
    last_action_failed: bool,
    same_action_count: i32,
}

pub struct HashNode<'a> { pub cls: &'a str, pub view_id: &'a str, pub text: &'a str, pub desc: &'a str, pub cx: i32, pub cy: i32 }

fn mix(mut h: i64, s: &str) -> i64 {
    if s.is_empty() { return h.wrapping_mul(31); }
    for u in s.encode_utf16() { h = h.wrapping_mul(31).wrapping_add(u as i64); }
    h
}

/// Mesmo resultado que o hash em Java (aritmética long com overflow).
pub fn screen_hash(present: bool, fg_pkg: &str, fg_class: &str, total_nodes: Option<i32>, nodes: &[HashNode]) -> i64 {
    if !present { return 0; }
    let mut h: i64 = 1125899906842597;
    h = mix(h, fg_pkg);
    h = mix(h, fg_class);
    if let Some(total) = total_nodes {
        h = h.wrapping_mul(31).wrapping_add(total as i64);
        for n in nodes.iter().take(45) {
            h = mix(h, n.cls);
            h = mix(h, n.view_id);
            h = mix(h, n.text);
            h = mix(h, n.desc);
            h = h.wrapping_mul(31).wrapping_add((n.cx / 24) as i64);
            h = h.wrapping_mul(31).wrapping_add((n.cy / 24) as i64);
        }
    }
    h
}

fn label_key(node: &Node) -> String { norm(&label_of(Some(node))) }

impl Guard {
    pub fn on_screen_inspected(&mut self, has_nodes: bool, hash: i64, prev_action: &str) -> Verdict {
        if !has_nodes {
            self.empty_tree_streak += 1;
            if self.empty_tree_streak >= MAX_EMPTY_TREES {
                return Verdict::Abort("⚠️ Ecrã inacessível",
                    "Não foram detetados elementos interativos após várias leituras (janela protegida ou vazia).".into());
            }
            return Verdict::Ok;
        }
        self.empty_tree_streak = 0;
        let was_wait = prev_action == "wait" || prev_action == "ask_user";
        if !was_wait && self.last_screen_hash != 0 {
            if hash == self.last_screen_hash {
                self.stagnant_steps += 1;
                if self.stagnant_steps >= MAX_STAGNANT_STEPS {
                    return Verdict::Abort("⚠️ Ciclo interrompido",
                        format!("O ecrã permaneceu inalterado durante {} passos consecutivos.", self.stagnant_steps));
                }
            } else {
                self.stagnant_steps = 0;
                self.same_action_count = 0;
            }
        }
        Verdict::Ok
    }

    #[allow(clippy::too_many_arguments)]
    pub fn record_refusal(&mut self, has_policy: bool, sig: &str, crit_pkg: &str, action: &str, target_pkg: &str,
                          fg_pkg: &str, node: Option<&Node>, x: i32, y: i32) {
        if has_policy {
            if !sig.is_empty() { self.refused_signatures.insert(sig.into()); }
            if !crit_pkg.is_empty() { self.refused_packages.insert(crit_pkg.to_lowercase()); }
        }
        if !target_pkg.is_empty() && (action == "open_app" || action == "launch") {
            self.refused_packages.insert(target_pkg.to_lowercase());
            self.refused_labels.insert(norm(target_pkg));
        }
        let fg = fg_pkg.to_lowercase();
        if let Some(n) = node {
            self.refused_spatial.insert(format!("{fg}|{},{}", n.cx / 48, n.cy / 48));
            let lbl = label_key(n);
            if !lbl.is_empty() && !lbl.starts_with('#') { self.refused_labels.insert(format!("{fg}|{lbl}")); }
        } else if x > 0 && y > 0 {
            self.refused_spatial.insert(format!("{fg}|{},{}", x / 48, y / 48));
        }
    }

    pub fn ask_user_refused_should_abort(&mut self) -> bool {
        self.ask_user_refusals += 1;
        self.ask_user_refusals >= 2
    }

    #[allow(clippy::too_many_arguments)]
    pub fn check_before(&mut self, has_policy: bool, sig: &str, crit_pkg: &str, action: &str, target_pkg: &str,
                        fg_pkg: &str, node: Option<&Node>, x: i32, y: i32, hash: i64) -> Verdict {
        let sig = if has_policy { sig } else { "" };
        let fg = fg_pkg.to_lowercase();
        let tgt = target_pkg.to_lowercase();
        let mut hit = (!sig.is_empty() && self.refused_signatures.contains(sig))
            || (!tgt.is_empty() && self.refused_packages.contains(&tgt))
            || (has_policy && !crit_pkg.is_empty() && self.refused_packages.contains(crit_pkg));
        if !hit {
            if let Some(n) = node {
                let spatial = format!("{fg}|{},{}", n.cx / 48, n.cy / 48);
                let lbl = label_key(n);
                hit = self.refused_spatial.contains(&spatial)
                    || (!lbl.is_empty() && (self.refused_labels.contains(&format!("{fg}|{lbl}")) || self.refused_labels.contains(&lbl)));
            } else if x > 0 && y > 0 {
                hit = self.refused_spatial.contains(&format!("{fg}|{},{}", x / 48, y / 48));
            }
        }
        if hit {
            return Verdict::Abort("🛑 Ação recusada",
                "O utilizador recusou esta ação e o agente tentou repeti-la; tarefa terminada por segurança.".into());
        }
        if action != "wait" && !sig.is_empty() && hash == self.last_screen_hash && sig == self.last_action_sig {
            self.same_action_count += 1;
            if self.last_action_failed {
                if self.same_action_count >= 2 {
                    return Verdict::Abort("⚠️ Elemento inacessível", "A mesma ação falhou repetidamente sem alterar o ecrã.".into());
                }
                return Verdict::Skip("Ação repetida bloqueada: esta mesma ação acabou de falhar no mesmo ecrã. Escolhe outro elemento, faz scroll ou conclui.".into());
            }
            if self.same_action_count >= 2 {
                return Verdict::Abort("⚠️ Ciclo detetado", "O agente repetiu a mesma ação várias vezes sem efeito visível no ecrã.".into());
            }
        }
        Verdict::Ok
    }

    pub fn after_execution(&mut self, signature: &str, ok: bool, hash_before: i64) -> Verdict {
        self.last_screen_hash = hash_before;
        self.last_action_sig = signature.to_string();
        self.last_action_failed = !ok;
        if !ok {
            self.consecutive_exec_failures += 1;
            if self.consecutive_exec_failures >= MAX_CONSECUTIVE_EXEC_FAILURES {
                return Verdict::Abort("⚠️ Falha na deteção de elementos", format!(
                    "Não foi possível interagir com os elementos do ecrã após {} tentativas consecutivas.",
                    self.consecutive_exec_failures));
            }
        } else {
            self.consecutive_exec_failures = 0;
        }
        Verdict::Ok
    }
}

pub fn encode(v: &Verdict) -> String {
    match v {
        Verdict::Ok => "OK".into(),
        Verdict::Skip(r) => format!("SKIP\u{1f}\u{1f}{r}"),
        Verdict::Abort(t, r) => format!("ABORT\u{1f}{t}\u{1f}{r}"),
    }
}

// ---------------------------------------------------------------- JNI

fn s(env: &mut JNIEnv, v: &JString) -> String {
    if v.is_null() { return String::new(); }
    env.get_string(v).map(String::from).unwrap_or_default()
}

fn guard<'a>(h: jlong) -> &'a mut Guard { unsafe { &mut *(h as *mut Guard) } }

fn ret(env: &mut JNIEnv, v: Verdict) -> jstring {
    env.new_string(encode(&v)).map(|j| j.into_raw()).unwrap_or(std::ptr::null_mut())
}

#[allow(clippy::too_many_arguments)]
fn node_from(env: &mut JNIEnv, has: jboolean, id: jint, text: &JString, desc: &JString, vid: &JString, cx: jint, cy: jint) -> Option<Node> {
    (has != 0).then(|| Node { id, text: s(env, text), desc: s(env, desc), view_id: s(env, vid), cx, cy, ..Default::default() })
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeNew(_: JNIEnv, _: JClass) -> jlong {
    Box::into_raw(Box::<Guard>::default()) as jlong
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeFree(_: JNIEnv, _: JClass, h: jlong) {
    if h != 0 { unsafe { drop(Box::from_raw(h as *mut Guard)) } }
}

/// strings = [cls, viewId, text, desc] × n ; centers = [cx, cy] × n
#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeHash<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>, present: jboolean, fg_pkg: JString<'l>, fg_class: JString<'l>,
    total: jint, strings: JObjectArray<'l>, centers: JIntArray<'l>,
) -> jlong {
    let (fp, fc) = (s(&mut env, &fg_pkg), s(&mut env, &fg_class));
    let mut owned: Vec<String> = Vec::new();
    let mut c: Vec<i32> = Vec::new();
    if !strings.is_null() {
        let len = env.get_array_length(&strings).unwrap_or(0);
        for i in 0..len {
            let o = env.get_object_array_element(&strings, i).ok();
            let v = o.map(|o| s(&mut env, &JString::from(o))).unwrap_or_default();
            owned.push(v);
        }
        let cl = env.get_array_length(&centers).unwrap_or(0) as usize;
        c = vec![0; cl];
        let _ = env.get_int_array_region(&centers, 0, &mut c);
    }
    let nodes: Vec<HashNode> = owned.chunks(4).zip(c.chunks(2)).map(|(f, p)| HashNode {
        cls: &f[0], view_id: &f[1], text: &f[2], desc: &f[3], cx: p[0], cy: p[1],
    }).collect();
    screen_hash(present != 0, &fp, &fc, (total >= 0).then_some(total), &nodes)
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeOnScreen<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>, h: jlong, has_nodes: jboolean, hash: jlong, prev: JString<'l>,
) -> jstring {
    let p = s(&mut env, &prev);
    let v = guard(h).on_screen_inspected(has_nodes != 0, hash, &p);
    ret(&mut env, v)
}

#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeRecordRefusal<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>, h: jlong, has_policy: jboolean, sig: JString<'l>, crit: JString<'l>,
    action: JString<'l>, target: JString<'l>, fg: JString<'l>, has_node: jboolean, id: jint,
    text: JString<'l>, desc: JString<'l>, vid: JString<'l>, cx: jint, cy: jint, x: jint, y: jint,
) {
    let (sg, cr, a, t, f) = (s(&mut env, &sig), s(&mut env, &crit), s(&mut env, &action), s(&mut env, &target), s(&mut env, &fg));
    let n = node_from(&mut env, has_node, id, &text, &desc, &vid, cx, cy);
    guard(h).record_refusal(has_policy != 0, &sg, &cr, &a, &t, &f, n.as_ref(), x, y);
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeAskUserRefused(_: JNIEnv, _: JClass, h: jlong) -> jboolean {
    guard(h).ask_user_refused_should_abort() as jboolean
}

#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeCheckBefore<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>, h: jlong, has_policy: jboolean, sig: JString<'l>, crit: JString<'l>,
    action: JString<'l>, target: JString<'l>, fg: JString<'l>, has_node: jboolean, id: jint,
    text: JString<'l>, desc: JString<'l>, vid: JString<'l>, cx: jint, cy: jint, x: jint, y: jint, hash: jlong,
) -> jstring {
    let (sg, cr, a, t, f) = (s(&mut env, &sig), s(&mut env, &crit), s(&mut env, &action), s(&mut env, &target), s(&mut env, &fg));
    let n = node_from(&mut env, has_node, id, &text, &desc, &vid, cx, cy);
    let v = guard(h).check_before(has_policy != 0, &sg, &cr, &a, &t, &f, n.as_ref(), x, y, hash);
    ret(&mut env, v)
}

#[no_mangle]
pub extern "system" fn Java_com_canorus_odysseus_AgentSessionGuard_nativeAfter<'l>(
    mut env: JNIEnv<'l>, _: JClass<'l>, h: jlong, sig: JString<'l>, ok: jboolean, hash: jlong,
) -> jstring {
    let sg = s(&mut env, &sig);
    let v = guard(h).after_execution(&sg, ok != 0, hash);
    ret(&mut env, v)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn refusals_loops_and_failures() {
        let mut g = Guard::default();
        let n = Node { text: "Enviar".into(), cx: 100, cy: 200, ..Default::default() };
        g.record_refusal(true, "tap|x", "", "tap", "", "com.whatsapp", Some(&n), 0, 0);
        assert!(matches!(g.check_before(true, "other", "", "tap", "", "com.whatsapp", Some(&n), 0, 0, 5), Verdict::Abort("🛑 Ação recusada", _)));
        assert_eq!(g.check_before(true, "z", "", "tap", "", "com.other", None, 0, 0, 5), Verdict::Ok);

        let mut g = Guard::default();
        assert_eq!(g.after_execution("s", false, 9), Verdict::Ok);
        assert!(matches!(g.check_before(true, "s", "", "tap", "", "", None, 0, 0, 9), Verdict::Skip(_)));
        assert!(matches!(g.check_before(true, "s", "", "tap", "", "", None, 0, 0, 9), Verdict::Abort("⚠️ Elemento inacessível", _)));

        let mut g = Guard::default();
        for _ in 0..2 { assert_eq!(g.on_screen_inspected(false, 0, ""), Verdict::Ok); }
        assert!(matches!(g.on_screen_inspected(false, 0, ""), Verdict::Abort(..)));
        assert!(g.ask_user_refused_should_abort() == false && g.ask_user_refused_should_abort());
        assert_eq!(screen_hash(false, "a", "b", None, &[]), 0);
        assert_eq!(mix(0, "é"), 233);
    }
}
