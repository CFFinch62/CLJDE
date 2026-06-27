(ns scratch.core)

(defn greet
  "Return a friendly greeting; handy for testing CLJDE's REPL eval."
  [name]
  (str "Hello, " name "!"))

(defn add
  "Add two numbers."
  [a b]
  (+ a b))

(comment
  ;; Put the cursor in a form below and press Ctrl+Enter to evaluate.
  (greet "Clojure")
  (add 2 3))
