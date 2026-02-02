import nltk
nltk.download('punkt_tab')

from nltk.tokenize import sent_tokenize

text = """Oranges grow on trees. Each orange has many seeds inside. The oranges are picked when they are big and round.
Farmers send the oranges to a place where juice is made. The oranges are washed. Then the oranges are squeezed. This takes out the juice.
The juice goes into big bottles. The bottles are sent to stores. You can find orange juice right next to the milk.
Orange juice is sweet. It is good to drink at breakfast. Some people drink it cold. Some like it with ice.
Orange juice comes from a fruit. The fruit grows on trees in warm places. Have you ever tasted fresh orange juice?"""

sentences = sent_tokenize(text)
print(sentences)