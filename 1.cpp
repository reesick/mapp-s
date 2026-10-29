#include <iostream>
#include <vector>
using namespace std;

bool safety(vector<vector<int>> a, vector<vector<int>> need,
            vector<int> avail, int n, int m, vector<int>& seq) {

    vector<bool> finish(n, false);
    vector<int> work = avail;

    while (seq.size() < n) {
        bool found = false;

        for (int i = 0; i < n; i++) {
            if (finish[i]) continue;

            bool possible = true;

            for (int j = 0; j < m; j++)
                if (need[i][j] > work[j])
                    possible = false;

            if (possible) {
                for (int j = 0; j < m; j++)
                    work[j] += a[i][j];

                finish[i] = true;
                seq.push_back(i);
                found = true;
            }
        }

        if (!found) return false;
    }

    return true;
}

bool request(int p, vector<int> req,
             vector<vector<int>>& a,
             vector<vector<int>>& need,
             vector<int>& avail, int n, int m) {

    for (int j = 0; j < m; j++)
        if (req[j] > need[p][j] || req[j] > avail[j])
            return false;

    for (int j = 0; j < m; j++) {
        avail[j] -= req[j];
        a[p][j] += req[j];
        need[p][j] -= req[j];
    }

    vector<int> seq;

    if (safety(a, need, avail, n, m, seq))
        return true;

    for (int j = 0; j < m; j++) {
        avail[j] += req[j];
        a[p][j] -= req[j];
        need[p][j] += req[j];
    }

    return false;
}

int main() {
    int n, m;

    cout << "Enter number of processes: ";
    cin >> n;

    cout << "Enter number of resources: ";
    cin >> m;

    vector<vector<int>> a(n, vector<int>(m));
    vector<vector<int>> max(n, vector<int>(m));
    vector<vector<int>> need(n, vector<int>(m));
    vector<int> avail(m);

    cout << "Enter Allocation Matrix:\n";
    for (int i = 0; i < n; i++)
        for (int j = 0; j < m; j++)
            cin >> a[i][j];

    cout << "Enter Maximum Matrix:\n";
    for (int i = 0; i < n; i++)
        for (int j = 0; j < m; j++)
            cin >> max[i][j];

    cout << "Enter Available Resources:\n";
    for (int j = 0; j < m; j++)
        cin >> avail[j];

    for (int i = 0; i < n; i++)
        for (int j = 0; j < m; j++)
            need[i][j] = max[i][j] - a[i][j];

    cout << "\nNeed Matrix:\n";
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < m; j++)
            cout << need[i][j] << " ";
        cout << endl;
    }

    vector<int> seq;

    if (!safety(a, need, avail, n, m, seq)) {
        cout << "\nSystem is in UNSAFE state.\n";
        return 0;
    }

    cout << "\nSystem is in SAFE state.\n";
    cout << "Safe Sequence: ";

    for (int i = 0; i < seq.size(); i++)
        cout << "P" << seq[i] << (i + 1 == seq.size() ? "\n" : " -> ");

    int p;
    cout << "\nEnter process making request: P";
    cin >> p;

    vector<int> req(m);
    cout << "Enter Request:\n";
    for (int j = 0; j < m; j++)
        cin >> req[j];

    if (request(p, req, a, need, avail, n, m))
        cout << "Request granted. System remains SAFE.\n";
    else
        cout << "Request cannot be granted.\n";

    return 0;
}