use odysseus_voice::policy::*;
use std::io::BufRead;
fn main() {
    for line in std::io::stdin().lock().lines() {
        let l = line.unwrap(); let f: Vec<&str> = l.split('\t').collect();
        let p = |i: usize| f[i].parse::<i32>().unwrap();
        let node = (f[5] == "1").then(|| Node { id: p(6), text: f[7].into(), desc: f[8].into(), view_id: f[9].into(), cx: p(10), cy: p(11), editable: f[12] == "1", password: f[13] == "1" });
        let label = node.as_ref().map(|n| label_of(Some(n))).unwrap_or_default();
        let d = evaluate(&Input { self_pkg: "com.canorus.odysseus", goal: f[0], action: f[1], fg_pkg: f[2], fg_class: f[3], target_pkg: f[4], node, x: p(14), y: p(15), text_or_url: f[16], confirm_critical: f[17] == "1", confirm_all_steps: f[18] == "1", submit: f[19] == "1", model_critical: f[20] == "1", model_reason: f[21] });
        println!("{}|{}|{}|{}|{}|{}|{}|{}", d.verdict, d.category, d.signature, d.critical_pkg, d.reason, norm(f[16]), normalize_http_url(f[16]).unwrap_or("null".into()), label);
    }
}
