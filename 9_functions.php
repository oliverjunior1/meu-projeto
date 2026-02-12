<?php
function greet($name) {
    return "Hello, " . $name . "!";
}
echo greet("Alice") . "<br>";
function add($a, $b) {
    return $a + $b;
}
echo "Soma: " . add(5, 10) . "<br>";
function factorial($n) {
    if ($n == 0) {
        return 1;
    } else {
        return $n * factorial($n - 1);
    }
}
echo "Fatorial de 5: " . factorial(5) . "<br>";
?>