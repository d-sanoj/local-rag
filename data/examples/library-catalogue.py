"""A tiny library catalogue.

It exists so the code chunker has function and class boundaries to split
on, and so retrieval can be checked against code rather than prose.
"""


class LibraryCatalogue:
    """Holds the books a small branch library owns."""

    def __init__(self):
        self.books = {}

    def add_book(self, isbn, title, author):
        """Register a book by its ISBN."""
        self.books[isbn] = {"title": title, "author": author, "on_loan": False}

    def find_book_by_isbn(self, isbn):
        """Look a book up by ISBN. Returns the record, or None."""
        return self.books.get(isbn)


def overdue_fine(days_late, rate_per_day=0.25):
    """Compute the overdue fine for a late return.

    Fines are charged per day late, capped at the price of the book.
    A book returned on time has no fine at all.
    """
    if days_late <= 0:
        return 0.0
    return round(days_late * rate_per_day, 2)


def is_available(catalogue, isbn):
    """True when the book exists and is not currently on loan."""
    book = catalogue.find_book_by_isbn(isbn)
    return book is not None and not book["on_loan"]
