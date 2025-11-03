use sales_sprint_log_analyzer::analyze_sales_sprints;
use std::collections::{HashMap, HashSet};

fn simplify(log: &str) -> Vec<(usize, usize, char)> {
    analyze_sales_sprints(log)
        .into_iter()
        .map(|o| (o.s, o.t, o.winner))
        .collect()
}

fn compute_single_char_expected(c: char) -> Vec<(usize, usize, char)> {
    vec![(1, 1, c)]
}

fn compute_identical_chars_expected(c: char, count: usize) -> Vec<(usize, usize, char)> {
    let mut result = Vec::new();
    for s in 1..=count {
        if count % s == 0 {
            let t = count / s;
            result.push((s, t, c));
        }
    }
    result.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    result
}

fn compute_prime_length_expected(c: char, count: usize) -> Vec<(usize, usize, char)> {
    vec![(1, count, c), (count, 1, c)]
}

fn compute_large_identical_expected(c: char, count: usize) -> Vec<(usize, usize, char)> {
    let mut result = Vec::new();
    for s in 1..=count {
        if count % s == 0 {
            let t = count / s;
            result.push((s, t, c));
        }
    }
    result.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    result
}

fn verify_no_early_termination(log: &str, results: &[(usize, usize, char)]) {
    for &(s, t, _) in results {
        let bytes = log.as_bytes();
        let mut a_in_sprint = 0usize;
        let mut b_in_sprint = 0usize;
        let mut total_sprints = 0usize;
        let mut i = 0usize;
        while i < bytes.len() {
            let c = bytes[i] as char;
            i += 1;
            if c == 'A' { a_in_sprint += 1; } else if c == 'B' { b_in_sprint += 1; }
            if a_in_sprint == t || b_in_sprint == t {
                total_sprints += 1;
                a_in_sprint = 0; b_in_sprint = 0;
                if total_sprints == s {
                    assert_eq!(i, bytes.len(), "Match (s={}, t={}) must end at log end", s, t);
                }
            }
        }
        assert_eq!(total_sprints, s, "Match (s={}, t={}) must have exactly s sprints", s, t);
        assert_eq!(a_in_sprint + b_in_sprint, 0, "No leftover partial sprint for (s={}, t={})", s, t);
    }
}

#[test]
fn test_empty_log_returns_no_outcomes() {
    let result = simplify("");
    let expected = vec![];
    assert_eq!(result, expected, "Empty log should return no outcomes");
}

#[test]
fn test_single_character_valid_match() {
    let result = simplify("A");
    let expected = compute_single_char_expected('A');
    assert_eq!(result, expected, "Single 'A' should yield exactly (1,1,'A')");
    verify_no_early_termination("A", &result);
}

#[test]
fn test_two_identical_characters_valid_matches() {
    let result = simplify("AA");
    let expected = compute_identical_chars_expected('A', 2);
    assert_eq!(result, expected, "Two 'A's should yield exactly [(1,2,'A'), (2,1,'A')]");
    verify_no_early_termination("AA", &result);
}

#[test]
fn test_two_different_characters_no_valid_matches() {
    let result = simplify("AB");
    let expected = vec![];
    assert_eq!(result, expected, "Two different characters 'AB' should yield no valid matches");
    verify_no_early_termination("AB", &result);
}

#[test]
fn test_three_characters_valid_matches() {
    let result = simplify("ABA");
    let expected = vec![(1, 2, 'A')];
    assert_eq!(result, expected, "Three characters 'ABA' should yield exactly [(1,2,'A')]");
    verify_no_early_termination("ABA", &result);
}

#[test]
fn test_four_identical_characters_multiple_matches() {
    let result = simplify("AAAA");
    let expected = compute_identical_chars_expected('A', 4);
    assert_eq!(result, expected, "Four 'A's should yield exactly [(1,4,'A'), (2,2,'A'), (4,1,'A')]");
    verify_no_early_termination("AAAA", &result);
}

#[test]
fn test_complex_pattern_valid_matches() {
    let result = simplify("AABBAA");
    let expected = vec![(1, 4, 'A')];
    assert_eq!(result, expected, "Complex pattern 'AABBAA' should yield exactly [(1,4,'A')]");
    verify_no_early_termination("AABBAA", &result);
}

#[test]
fn test_alternating_pattern_no_valid_matches() {
    let result = simplify("ABABAB");
    let expected = vec![];
    assert_eq!(result, expected, "Alternating pattern 'ABABAB' should yield no valid matches");
    verify_no_early_termination("ABABAB", &result);
}

#[test]
fn test_prime_length_all_same_characters() {
    let result = simplify("AAAAA");
    let expected = compute_prime_length_expected('A', 5);
    assert_eq!(result, expected, "Prime length all 'A's should yield exactly [(1,5,'A'), (5,1,'A')]");
    verify_no_early_termination("AAAAA", &result);
}

#[test]
fn test_large_number_identical_characters() {
    let result = simplify("AAAAAAAAAAAA");
    let expected = compute_large_identical_expected('A', 12);
    assert_eq!(result, expected, "12 'A's should yield exactly 6 valid matches");
    verify_no_early_termination("AAAAAAAAAAAA", &result);
}

#[test]
fn test_mixed_pattern_b_winner() {
    let result = simplify("AABBB");
    let expected = vec![(1, 3, 'B')];
    assert_eq!(result, expected, "Mixed pattern 'AABBB' should yield exactly [(1,3,'B')]");
    verify_no_early_termination("AABBB", &result);
}

#[test]
fn test_off_by_one_length_edge_case() {
    let result = simplify("AAAB");
    let expected = vec![];
    assert_eq!(result, expected, "Off-by-one length 'AAAB' should yield no valid matches");
    verify_no_early_termination("AAAB", &result);
}

#[test]
fn test_palindrome_pattern() {
    let result = simplify("ABABA");
    let expected = vec![(1, 3, 'A')];
    assert_eq!(result, expected, "Palindrome 'ABABA' should yield exactly [(1,3,'A')]");
    verify_no_early_termination("ABABA", &result);
}

#[test]
fn test_single_character_b() {
    let result = simplify("B");
    let expected = compute_single_char_expected('B');
    assert_eq!(result, expected, "Single 'B' should yield exactly (1,1,'B')");
    verify_no_early_termination("B", &result);
}

#[test]
fn test_all_b_characters() {
    let result = simplify("BBBBBB");
    let expected = compute_identical_chars_expected('B', 6);
    assert_eq!(result, expected, "Six 'B's should yield exactly 4 valid matches");
    verify_no_early_termination("BBBBBB", &result);
}

#[test]
fn test_impossible_split_pattern() {
    let result = simplify("AABB");
    let expected = vec![];
    assert_eq!(result, expected, "Impossible split pattern 'AABB' should yield no valid matches");
    verify_no_early_termination("AABB", &result);
}

#[test]
fn test_maximum_length_edge_case() {
    let long_string = "A".repeat(100);
    let result = simplify(&long_string);
    
    assert!(!result.is_empty(), "Long string should have valid matches");
    
    for &(_s, _t, winner) in &result {
        assert_eq!(winner, 'A', "Winner should be 'A' for all-A string");
    }
    
    verify_no_early_termination(&long_string, &result);
}

#[test]
fn test_sorting_order() {
    let result = simplify("AAAA");
    assert_eq!(result.len(), 3, "Should have exactly 3 results");
    
    for i in 0..result.len() - 1 {
        let (s1, t1, _) = result[i];
        let (s2, t2, _) = result[i + 1];
        
        if s1 == s2 {
            assert!(t1 <= t2, "When s values are equal, t should be sorted");
        } else {
            assert!(s1 < s2, "s values should be sorted");
        }
    }
}

#[test]
fn test_no_duplicate_results() {
    let result = simplify("AAAA");
    let mut seen = HashSet::new();
    
    for &(s, t, winner) in &result {
        let key = (s, t, winner);
        assert!(!seen.contains(&key), "No duplicate results should exist");
        seen.insert(key);
    }
}

#[test]
fn test_winner_determination() {
    let result = simplify("AABBB");
    
    for &(s, t, winner) in &result {
        let mut sprints_won = HashMap::new();
        let mut current_sprint = Vec::new();
        
        for c in "AABBB".chars() {
            current_sprint.push(c);
            let count_a = current_sprint.iter().filter(|&&x| x == 'A').count();
            let count_b = current_sprint.iter().filter(|&&x| x == 'B').count();
            
            if count_a == t || count_b == t {
                let sprint_winner = if count_a == t { 'A' } else { 'B' };
                *sprints_won.entry(sprint_winner).or_insert(0) += 1;
                current_sprint.clear();
                
                if sprints_won.values().any(|&count| count >= s) {
                    let expected_winner = sprints_won.iter()
                        .max_by_key(|&(_, &count)| count)
                        .map(|(&k, _)| k)
                        .unwrap();
                    assert_eq!(winner, expected_winner, "Winner should match simulation");
                    break;
                }
            }
        }
    }
}

#[test]
fn test_invalid_characters() {
    let result = simplify("AXB");
    let expected = vec![];
    assert_eq!(result, expected, "Invalid character 'X' should be ignored and yield no valid matches");
    verify_no_early_termination("AXB", &result);
}

#[test]
fn test_mixed_invalid_valid_characters() {
    let result = simplify("A!B@C#D");
    let expected = vec![];
    assert_eq!(result, expected, "Mixed invalid and valid characters should yield no valid matches");
    verify_no_early_termination("A!B@C#D", &result);
}

#[test]
fn test_performance_large_input() {
    let large_string = "A".repeat(1000);
    let result = simplify(&large_string);
    
    assert!(!result.is_empty(), "Large input should have valid matches");
    
    for &(_s, _t, winner) in &result {
        assert_eq!(winner, 'A', "Winner should be 'A' for all-A string");
    }
    
    verify_no_early_termination(&large_string, &result);
}

#[test]
fn test_unicode_characters() {
    let result = simplify("A\u{00E1}B\u{00E9}");
    let expected = vec![];
    assert_eq!(result, expected, "Unicode string 'AáBé' should behave like 'AB' and yield no valid matches");
    verify_no_early_termination("A\u{00E1}B\u{00E9}", &result);
}

#[test]
fn test_unicode_with_valid_matches() {
    let result = simplify("A\u{00E1}A\u{00E9}B\u{00F1}B\u{00F3}B"); 
    let expected = vec![(1, 3, 'B')];
    assert_eq!(result, expected, "Unicode string 'AáAéBñBóB' should behave like 'AABBB' and yield valid matches");
    verify_no_early_termination("A\u{00E1}A\u{00E9}B\u{00F1}B\u{00F3}B", &result);
}

#[test]
fn test_case_sensitivity() {
    let result = simplify("AaBb");
    let expected = vec![];
    assert_eq!(result, expected, "Lowercase letters should be ignored and yield no valid matches");
    verify_no_early_termination("AaBb", &result);
}

