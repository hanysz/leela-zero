
# Turn a tracefile CSV into an SGF file with a variation for each playout

# Usage:
#   python tracefile_to_sgf.py input.sgf trace.csv output.sgf [numplayouts]
# where:
#   input.sgf is the original file that the trace was made from
#   output.csv is the CSV file with the trace of the playouts
#   output.sgf is the new SGF file to be created
#   numplayouts (optional parameter) is the number of playouts to add to the SGF
#    if omited, use all playouts in the CSV

import sys, os, shlex, string, re, pandas, math
from sgfmill import sgf
# Handy reference: https://mjw.woodcraft.me.uk/sgfmill/doc/1.1.1/examples.html

digits=4 # show all floating point numbers to 4 decimal places

if (len(sys.argv) not in [4,5]):
  sys.exit("Usage: python tracefile_to_sgf.py input.sgf trace.csv output.sgf [numplayouts]")

input_filename = sys.argv[1]
trace_filename = sys.argv[2]
output_filename = sys.argv[3]
if len(sys.argv) == 5:
  maxplayout = int(sys.argv[4])
else:
  maxplayout = 0

if (os.path.exists(output_filename)):
  sys.exit("Error: output file " + output_filename + " already exists.")

with open(input_filename, "rb") as f:
  game = sgf.Sgf_game.from_bytes(f.read())
root_node = game.get_last_node()

board_LETTERS = string.ascii_uppercase # 'A' to 'Z'
board_LETTERS = board_LETTERS.replace("I", "") # 'i' isn't used as a coordinate

def text_to_move(m):
  # Input: m is a move in the form of text, e.g. F1
  # Output: the same move as coordinates, e.g. (0,5) = 0 up, 5 across
  return(int(m[1:])-1, board_LETTERS.find(m[0]))

def flip(colour):
  if colour == 'w':
    return 'b'
  else:
    return 'w'

def numstr(x): # convert number to string with rounding
  return str(round(x, digits))

def append_comment_text(node, text):
  # sgfmill's add_comment_text inserts two newline characters
  #   when there's an existing comment
  # I just want to append the raw text
  if node.has_property("C"):
    node.set("C", node.get("C")+text)
  else:
    node.add_comment_text(text)

def add_visit(node):
  # use a custom XV tag to count visits as we go,
  # so that we're able to insert the total visit count when we're finished
  if node.has_property("XV"):
    node.set("XV", str(int(node.get("XV"))+1))
  else:
    node.set("XV", "1")

df = pandas.read_csv(trace_filename, index_col=False)

append_comment_text(root_node, "Initial value +" + numstr(df.loc[0, "value"]) + "\n")
playout_numbers = df["playout"].to_list()
playouts_reversed = playout_numbers.copy()
playouts_reversed.reverse() # easiest way to find index of last occurence of something
n = max(playout_numbers)
if maxplayout >0:
  n = min(n, maxplayout)
nrow = len(playout_numbers)
for i in range(1, n+1):
  current_node = root_node
  colour = current_node.get_move()[0]
  # Need to keep track of CSV file line numbers for both the "explore" and "update" bits
  # because "explore" has the policy values whereas
  # "update" has the updated evals and LCB.
  explore_row = playout_numbers.index(i) # row number of the "explore" line for this playout
  explore_row -= 1 # take off one because we don't explore the root
  update_row = nrow - playouts_reversed.index(i) - 1
  # This is the row number of the last "update" line for playout number i

  while df.loc[update_row,"operation"] == 'update':
    move = df.loc[update_row,"move"]
    if move != "pass": # pass is the root node, otherwise we need to move down the tree
      # Check whether the move has already been visited
      move = text_to_move(move) # convert from e.g. B7 to (6,1)
      colour = flip(colour)
      found_move = False
      for child in current_node: # may be empty, that's OK
        if child.get_move()[1] == move:
          next_node = child
          found_move = True
      if found_move:
        current_node = next_node
      else:
        current_node = current_node.new_child()
        current_node.set_move(colour, move)
        # On the first visit only, add the policy value (it won't change later!)
        if i==1: # the file has an extra line for initialising the root on playout 1
          explore_row += 1;
        append_comment_text(current_node, "policy=" +
                              numstr(df.loc[explore_row, "policy"]) + "\n")
    append_comment_text(current_node, "Playout " + str(i) + " value=" +
                              numstr(df.loc[update_row, "value"]) + ", LCB=" +
                              numstr(df.loc[update_row, "lcb"]) + "\n")
    explore_row += 1
    update_row -= 1
    add_visit(current_node)

def add_visits_to_comments(node):
  text = node.get("C")
  visits = node.get("XV")
  visit_text = visits + " visit"
  if (visits>'1'):
    visit_text += "s"
  visit_text += ", "
  node.set("C", visit_text+text)
  node.unset("XV") # don't need these tags in the output SGF
  for child in node:
    add_visits_to_comments(child)

add_visits_to_comments(root_node)

with open(output_filename, "wb") as f:
  f.write(game.serialise())
