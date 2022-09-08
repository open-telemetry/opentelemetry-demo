use core::fmt;

use opentelemetry::{trace::get_active_span, KeyValue};

#[derive(Debug, Default)]
pub struct Quote {
    pub dollars: i64,
    pub cents: i32,
}

// TODO: Check product catalog for price on each item (will likley need item ID)
pub fn create_quote_from_count(count: u32) -> Quote {
    let f = if count == 0 {
        0.0
    } else {
        8.99 * (count as f64)
    };
    get_active_span(|span| {
        let q = create_quote_from_float(f);
        span.set_attribute(KeyValue::new("app.shipping.items.count", count as i64));
        span.set_attribute(KeyValue::new("app.shipping.cost.total", format!("{}", q)));
        q
    })
}

pub fn create_quote_from_float(value: f64) -> Quote {
    Quote {
        dollars: value.floor() as i64,
        cents: ((value * 100_f64) as i32) % 100,
    }
}

impl fmt::Display for Quote {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}.{}", self.dollars, self.cents)
    }
}
