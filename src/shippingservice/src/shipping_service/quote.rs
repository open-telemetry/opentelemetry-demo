#[derive(Debug, Default)]
pub struct Quote {
    pub dollars: i64,
    pub cents: i32,
}

pub fn create_quote_from_count(count: u32) -> Quote {
    let f = if count == 0 { 0.0 } else { 8.99 };
    create_quote_from_float(f)
}

pub fn create_quote_from_float(value: f64) -> Quote {
    Quote {
        dollars: value.floor() as i64,
        cents: (value.rem_euclid(1_f64) * 100_f64) as i32,
    }
}