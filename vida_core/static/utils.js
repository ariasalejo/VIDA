function reverseString(str) {
    return String(str).split('').reverse().join('');
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { reverseString };
}

if (typeof window !== 'undefined') {
    window.reverseString = reverseString;
}