// Sample JS file for testing

function greet(name) {
    return `Hello, ${name}!`;
}

const add = (a, b) => {
    return a + b;
};

const multiply = function(x, y) {
    return x * y;
};

class Calculator {
    constructor(initial) {
        this.value = initial || 0;
    }

    add(n) {
        this.value += n;
        return this;
    }

    subtract(n) {
        this.value -= n;
        return this;
    }

    result() {
        return this.value;
    }
}

async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}

export const formatDate = (date) => {
    return date.toISOString().split('T')[0];
};
