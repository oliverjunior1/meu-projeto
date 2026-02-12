
<?php
/*
Crie um arquivo desafio.php com:
Uma variável $numero
Verifique:
Se for maior que 10 → "Número alto"
Senão → "Número baixo"
Faça um loop que imprima de 1 até o número
*/
$numero = 15;
if ($numero > 10) {
	echo "Número alto";	
}
else {
	echo "Número baixo";
}

for ($i =0 ; $i < $numero; $i++) {
echo $i. "<br>";
} 
?>