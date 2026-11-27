use odysseus_voice::guard::*;
use odysseus_voice::policy::Node;
use std::io::BufRead;
fn v(x: &Verdict) -> String {
    match x { Verdict::Ok => "true/false/null/null".into(), Verdict::Skip(r) => format!("false/false/null/{r}"), Verdict::Abort(t, r) => format!("false/true/{t}/{r}") }
}
fn node(f: &[&str], i: usize) -> Option<Node> {
    (f[i] == "1").then(|| Node { id: f[i+1].parse().unwrap(), text: f[i+2].into(), desc: f[i+3].into(), view_id: f[i+4].into(), cx: f[i+5].parse().unwrap(), cy: f[i+6].parse().unwrap(), ..Default::default() })
}
fn main() {
    let mut g = Guard::default();
    for line in std::io::stdin().lock().lines() {
        let l = line.unwrap(); let f: Vec<&str> = l.split('\t').collect();
        let i = |k: usize| f[k].parse::<i32>().unwrap();
        match f[0] {
            "NEW" => { g = Guard::default(); println!("new"); }
            "HASH" => {
                let k: i32 = f[4].parse().unwrap();
                let names: Vec<(String, String, String, String, i32, i32)> = (0..k.max(0)).map(|j| (format!("cls{}", j % 3), if j % 4 == 0 { String::new() } else { format!("id/{j}") }, format!("{}{}", f[5], j), if j % 2 == 0 { String::new() } else { "dé".into() }, j * 37 % 400, j * 91 % 900)).collect();
                let nodes: Vec<HashNode> = names.iter().map(|n| HashNode { cls: &n.0, view_id: &n.1, text: &n.2, desc: &n.3, cx: n.4, cy: n.5 }).collect();
                let h = screen_hash(f[1] == "1", f[2], f[3], (k >= 0).then_some(k), &nodes);
                let has = f[1] == "1" && k > 0;
                println!("hash {} {}", h, v(&g.on_screen_inspected(has, f[6].parse().unwrap(), f[7])));
            }
            "REF" => { let n = node(&f, 9); g.record_refusal(f[1] == "1", f[2], f[3], f[4], f[5], f[6], n.as_ref(), i(7), i(8)); println!("ref"); }
            "ASK" => println!("ask {}", g.ask_user_refused_should_abort()),
            "CHK" => { let n = node(&f, 9); println!("chk {}", v(&g.check_before(f[1] == "1", f[2], f[3], f[4], f[5], f[6], n.as_ref(), i(7), i(8), f[16].parse().unwrap()))); }
            "AFT" => println!("aft {}", v(&g.after_execution(f[1], f[2] == "1", f[3].parse().unwrap()))),
            _ => {}
        }
    }
}
